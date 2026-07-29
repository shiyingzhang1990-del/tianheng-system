"""
问答API路由
处理智能问答相关的请求 — 基于文档检索 + 多认知框架
"""
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from datetime import datetime
import json
import requests

from models import db
from models.qa_record import QARecord
from models.document import Document
from services.prompts import get_framework, list_frameworks

qa_bp = Blueprint('qa', __name__)

DEFAULT_USER_ID = 1


def search_documents(question: str, top_n: int = 5):
    """关键词检索 — 先查标题/标签（快），命中后再加载全文摘要"""
    keywords = [w.strip() for w in question.replace('？', ' ').replace('?', ' ')
                .replace('，', ' ').replace(',', ' ').replace('。', ' ')
                .replace('！', ' ').split() if len(w.strip()) >= 2]

    if not keywords:
        return []

    # 先只查标题和标签（不加载 full_text，快速）
    all_docs = Document.query.filter_by(
        user_id=DEFAULT_USER_ID, status='active'
    ).with_entities(
        Document.id, Document.title, Document.author, Document.tags, Document.full_text
    ).all()

    if not all_docs:
        return []

    # 内存中快速打分
    scored = []
    for row in all_docs:
        doc_id, title, author, tags, full_text = row
        searchable = f"{title} {tags or ''}"
        score = sum(searchable.lower().count(kw.lower()) for kw in keywords)

        # 只有标题/标签命中时才检查全文
        text = full_text or ''
        if text:
            text_lower = text.lower()
            for kw in keywords:
                score += text_lower.count(kw.lower())

        if score == 0:
            continue

        snippet = ''
        if text:
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

        scored.append({
            'id': doc_id,
            'title': title,
            'author': author or '',
            'score': score,
            'snippets': [snippet] if snippet else []
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


def build_prompt(question: str, context: str | None, framework_id: str = 'epic') -> str:
    """构建完整的 Prompt（根据指定的认知框架）"""
    fw = get_framework(framework_id)
    template = fw['template']

    if context:
        context_section = f"""# 参考资料（来自用户已上传的文档）

{context}

请基于以上参考资料进行分析。"""
    else:
        context_section = """# 注意
当前知识库中暂无相关文档。请基于你自己的知识储备进行分析。
建议在回答开头说明：此回答基于通用知识，未参考用户上传的文档。"""

    return template.format(
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
    """提问并获取答案（流式输出）— 文档检索 + 认知框架"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        framework_id = data.get('framework', 'epic')

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        if len(question) > 2000:
            return jsonify({'error': '问题长度不能超过2000字符'}), 400

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
        prompt = build_prompt(question, context, framework_id)

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
    """提问并获取答案（非流式）— 文档检索 + 认知框架"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        framework_id = data.get('framework', 'epic')

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        if len(question) > 2000:
            return jsonify({'error': '问题长度不能超过2000字符'}), 400

        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')

        if not api_key:
            return jsonify({'error': '请先配置 DeepSeek API Key'}), 400

        # 搜索相关文档
        search_results = search_documents(question)
        context = build_context(search_results)
        prompt = build_prompt(question, context, framework_id)

        print(f"收到问题: {question} (框架: {framework_id})")
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


@qa_bp.route('/frameworks', methods=['GET'])
def get_frameworks():
    """获取可用的认知框架列表"""
    try:
        frameworks = list_frameworks()
        return jsonify({'frameworks': frameworks, 'default': 'epic'})
    except Exception as e:
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
