"""
问答API路由
处理智能问答相关的请求 — 基于文档检索 + EPIC认知框架
"""
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from datetime import datetime
import json
import requests

from models import db
from models.qa_record import QARecord
from models.document import Document

qa_bp = Blueprint('qa', __name__)

DEFAULT_USER_ID = 1

# EPIC 认知框架 Prompt 模板
EPIC_PROMPT_TEMPLATE = """你是一位顶尖的经济管理领域思想家，具备深刻的洞察力和原创性思维。

{context_section}

# 用户问题
{question}

# E-P-I-C 生成式认知逻辑链条

请运用 **E-P-I-C 认知框架** 来深度分析和回答问题，展现你的思想深度：

## 第一环 (E): 本质洞察 - 寻找张力

**核心任务**：从参考资料中挖掘出"根本性张力"（Fundamental Tension）

**思考路径**：
1. **悖论扫描**：识别资料中的矛盾、冲突或不一致性（理论vs现实、宏观vs微观、过去vs现在）
2. **异常信号放大**：关注"意外发现"和"局外点"，将其作为颠覆性洞察的突破口
3. **问题升维**：将具体问题升维至"制度-结构-人性"的深层追问

**输出目标**：提炼出一个极具张力的核心问题，抓住智识要害

## 第二环 (P): 模式提炼 - 锻造概念

**核心任务**：为发现的张力创造"原创性概念模型"

**思考路径**：
1. **过程抽象**：将案例演化抽象为普适性的"阶段"和"核心机制"
2. **概念命名**：为独特模式赋予简洁、形象、富有理论意涵的新名字
3. **模型建构**：构建可视化、结构化的理论框架（如矩阵、流程图、整合框架）

**输出目标**：创造一个原创的理论模型和核心构念

## 第三环 (I): 意涵衍生 - 情景推演

**核心任务**：基于新模型进行前瞻性的"多维情景推演"

**思考路径**：
1. **理论推演**：用新模型审视其他领域，得出颠覆性理论假设
2. **实践推演**：为不同实践者（CEO、政策制定者、投资者）提供差异化的"行动剧本"
3. **边界推演**：明确模型的适用条件和失效边界，预见未来挑战

**输出目标**：提供具有前瞻性和可操作性的战略洞察

## 第四环 (C): 语境重构 - 定义贡献

**核心任务**：阐述这个分析如何"重塑认知语境"

**思考路径**：
1. **贡献定位**：在宏大的知识地图中定位这个洞察的位置
2. **议程设置**：提出能引领未来思考方向的"新问题"和"新议程"
3. **价值升华**：回归时代命题，彰显思想格局和社会价值

**输出目标**：重新定义问题的认知框架，开启新探索

---

## 回答要求

1. **深度优先**：追求洞察的深刻性，而非表面的全面性
2. **创造性**：不满足于应用现有理论，要创造新的理论框架
3. **结构化**：使用Markdown格式（标题、列表、粗体、代码块、表格等）清晰呈现思维层次
4. **前瞻性**：不仅解释过去，更要塑造对未来的理解
5. **基于事实**：所有洞察必须源自参考资料，不编造信息
6. **承认局限**：如果资料不足以支撑深度分析，明确说明

请开始你的E-P-I-C认知分析："""


def search_documents(question: str, top_n: int = 5):
    """在已上传的文档中做关键词检索（SQLite LIKE 数据库层匹配，快速）

    用 SQL LIKE 在数据库层做关键词匹配，避免加载全部文档全文到内存。
    """
    keywords = [w.strip() for w in question.replace('？', ' ').replace('?', ' ')
                .replace('，', ' ').replace(',', ' ').replace('。', ' ')
                .replace('！', ' ').split() if len(w.strip()) >= 2]

    if not keywords:
        return []

    # 在数据库层用 LIKE 匹配，只查出相关文档（不加载 full_text）
    conditions = []
    for kw in keywords:
        like = f'%{kw}%'
        conditions.append(Document.title.ilike(like))
        conditions.append(Document.tags.ilike(like))
        conditions.append(Document.full_text.ilike(like))

    candidates = Document.query.filter(
        Document.user_id == DEFAULT_USER_ID,
        Document.status == 'active',
        db.or_(*conditions)
    ).all()

    if not candidates:
        return []

    # 只对候选文档做评分和摘要提取
    scored = []
    for doc in candidates:
        title_and_tags = f"{doc.title} {doc.tags or ''}"
        score = sum(title_and_tags.lower().count(kw.lower()) for kw in keywords)

        text = doc.full_text or ''
        if text:
            text_lower = text.lower()
            for kw in keywords:
                score += text_lower.count(kw.lower())

            # 快速找最佳摘要位置（取第一个关键词出现的位置附近）
            best_pos = 0
            for kw in keywords:
                pos = text_lower.find(kw.lower())
                if pos != -1:
                    best_pos = pos
                    break

            start = max(0, best_pos - 150)
            snippet = text[start:start + 600]
            if start > 0:
                snippet = '...' + snippet
            if start + 600 < len(text):
                snippet = snippet + '...'
            snippets = [snippet]
        else:
            snippets = []

        scored.append({
            'id': doc.id,
            'title': doc.title,
            'author': doc.author or '',
            'score': score,
            'snippets': snippets[:3]
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:top_n]


def build_context(search_results):
    """构建给AI的参考资料上下文"""
    if not search_results:
        return None

    parts = []
    for i, r in enumerate(search_results):
        parts.append(f"### 参考资料{i + 1}：《{r['title']}》")
        if r['author']:
            parts.append(f"作者：{r['author']}")
        for j, snippet in enumerate(r['snippets'][:2]):
            parts.append(f"\n相关片段{j + 1}：\n{snippet}\n")

    return '\n'.join(parts)


def build_epic_prompt(question: str, context: str | None) -> str:
    """构建完整的 EPIC Prompt"""
    if context:
        context_section = f"""# 参考资料（来自用户已上传的文档）

{context}

请基于以上参考资料，运用 E-P-I-C 认知框架深度分析和回答问题。"""
    else:
        context_section = """# 注意
当前知识库中暂无相关文档。请基于你自己的知识储备，运用 E-P-I-C 认知框架深度分析和回答问题。
建议在回答开头说明：此回答基于通用知识，未参考用户上传的文档。"""

    return EPIC_PROMPT_TEMPLATE.format(
        context_section=context_section,
        question=question
    )


def call_deepseek_stream(api_key, api_url, messages):
    """调用 DeepSeek API 流式生成"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'stream': True,
        'temperature': 0.3,
        'max_tokens': 4000
    }

    try:
        resp = requests.post(
            f"{api_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=120
        )

        if resp.status_code != 200:
            yield 'error', f'API请求失败 (HTTP {resp.status_code})'
            return

        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data_str = line[6:]
                if data_str == '[DONE]':
                    break
                try:
                    data = json.loads(data_str)
                    delta = data.get('choices', [{}])[0].get('delta', {})
                    if 'reasoning_content' in delta and delta['reasoning_content']:
                        yield 'reasoning', delta['reasoning_content']
                    if 'content' in delta and delta['content']:
                        yield 'content', delta['content']
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    except requests.exceptions.Timeout:
        yield 'error', 'AI响应超时，请稍后重试'
    except requests.exceptions.RequestException as e:
        yield 'error', f'网络连接失败: {str(e)}'


@qa_bp.route('/ask-stream', methods=['POST'])
def ask_question_stream():
    """提问并获取答案（流式输出）— 文档检索 + EPIC 框架"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        if len(question) > 1000:
            return jsonify({'error': '问题长度不能超过1000字符'}), 400

        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')

        if not api_key:
            def no_key_generate():
                yield f"data: {json.dumps({'type': 'error', 'data': '请先配置 DeepSeek API Key'}, ensure_ascii=False)}\n\n"
            return Response(
                stream_with_context(no_key_generate()),
                mimetype='text/event-stream'
            )

        # 搜索相关文档
        search_results = search_documents(question)
        context = build_context(search_results)
        prompt = build_epic_prompt(question, context)

        print(f"收到问题（流式）: {question}")
        print(f"匹配文档数: {len(search_results)}")

        messages = [{'role': 'user', 'content': prompt}]

        def generate():
            start_time = datetime.now()
            full_answer = []
            sources = [{'id': r['id'], 'title': r['title'], 'author': r['author']}
                       for r in search_results]

            try:
                yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"

                for chunk_type, chunk_content in call_deepseek_stream(api_key, api_url, messages):
                    if chunk_type == 'content':
                        full_answer.append(chunk_content)
                        yield f"data: {json.dumps({'type': 'content', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                    elif chunk_type == 'error':
                        yield f"data: {json.dumps({'type': 'error', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                        return

                response_time = (datetime.now() - start_time).total_seconds()
                answer_text = ''.join(full_answer)

                if answer_text:
                    qa_record = QARecord(
                        user_id=DEFAULT_USER_ID,
                        question=question,
                        answer=answer_text,
                        sources=json.dumps(sources, ensure_ascii=False),
                        response_time=response_time
                    )
                    db.session.add(qa_record)
                    db.session.commit()

                    yield f"data: {json.dumps({'type': 'done', 'data': {'qa_id': qa_record.id, 'response_time': response_time}}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'done', 'data': {'response_time': response_time}}, ensure_ascii=False)}\n\n"

            except Exception as e:
                print(f"流式生成出错: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        print(f"处理流式问题时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@qa_bp.route('/ask', methods=['POST'])
def ask_question():
    """提问并获取答案（非流式）— 文档检索 + EPIC 框架"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        if len(question) > 1000:
            return jsonify({'error': '问题长度不能超过1000字符'}), 400

        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')

        if not api_key:
            return jsonify({'error': '请先配置 DeepSeek API Key'}), 400

        # 搜索相关文档
        search_results = search_documents(question)
        context = build_context(search_results)
        prompt = build_epic_prompt(question, context)

        print(f"收到问题: {question}")
        print(f"匹配文档数: {len(search_results)}")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        payload = {
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.3,
            'max_tokens': 4000
        }

        start_time = datetime.now()

        resp = requests.post(
            f"{api_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )

        response_time = (datetime.now() - start_time).total_seconds()

        if resp.status_code != 200:
            return jsonify({'error': f'AI API请求失败 (HTTP {resp.status_code})'}), 500

        result = resp.json()
        answer = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        sources = [{'id': r['id'], 'title': r['title'], 'author': r['author']}
                   for r in search_results]

        qa_record = QARecord(
            user_id=DEFAULT_USER_ID,
            question=question,
            answer=answer,
            sources=json.dumps(sources, ensure_ascii=False),
            response_time=response_time
        )
        db.session.add(qa_record)
        db.session.commit()

        return jsonify({
            'success': True,
            'qa_id': qa_record.id,
            'question': question,
            'answer': answer,
            'sources': sources,
            'response_time': response_time,
            'timestamp': qa_record.created_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        print(f"处理问题时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@qa_bp.route('/history', methods=['GET'])
def get_history():
    """获取问答历史记录"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = QARecord.query.filter_by(user_id=DEFAULT_USER_ID)\
            .order_by(QARecord.created_time.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        records = []
        for record in pagination.items:
            records.append({
                'id': record.id,
                'question': record.question,
                'answer': record.answer,
                'sources': record.sources,
                'response_time': record.response_time,
                'created_time': record.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                'satisfaction': record.satisfaction
            })

        return jsonify({
            'records': records,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        })

    except Exception as e:
        print(f"获取历史记录时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@qa_bp.route('/<int:qa_id>', methods=['GET'])
def get_qa_record(qa_id):
    """获取单条问答记录详情"""
    try:
        record = QARecord.query.get(qa_id)

        if not record:
            return jsonify({'error': '记录不存在'}), 404

        return jsonify({
            'id': record.id,
            'question': record.question,
            'answer': record.answer,
            'sources': record.sources,
            'response_time': record.response_time,
            'created_time': record.created_time.strftime('%Y-%m-%d %H:%M:%S'),
            'satisfaction': record.satisfaction
        })

    except Exception as e:
        print(f"获取问答记录时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@qa_bp.route('/<int:qa_id>', methods=['DELETE'])
def delete_qa_record(qa_id):
    """删除问答记录"""
    try:
        record = QARecord.query.get(qa_id)

        if not record:
            return jsonify({'error': '记录不存在'}), 404

        db.session.delete(record)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '记录已删除'
        })

    except Exception as e:
        print(f"删除问答记录时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@qa_bp.route('/<int:qa_id>/satisfaction', methods=['POST'])
def rate_satisfaction(qa_id):
    """对问答结果进行满意度评分"""
    try:
        data = request.get_json()
        satisfaction = data.get('satisfaction')

        if satisfaction not in [1, 2, 3, 4, 5]:
            return jsonify({'error': '满意度评分必须在1-5之间'}), 400

        record = QARecord.query.get(qa_id)

        if not record:
            return jsonify({'error': '记录不存在'}), 404

        record.satisfaction = satisfaction
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '评分已保存'
        })

    except Exception as e:
        print(f"保存满意度评分时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500
