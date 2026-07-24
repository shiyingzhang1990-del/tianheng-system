"""
问答API路由
处理智能问答相关的请求
"""
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from datetime import datetime
import json

from models import db
from models.qa_record import QARecord
from services.vector_store import get_vector_store
from services.rag_service import get_rag_service

# 创建蓝图
qa_bp = Blueprint('qa', __name__)

# 默认用户ID（无认证模式）
DEFAULT_USER_ID = 1


@qa_bp.route('/ask', methods=['POST'])
def ask_question():
    """提问并获取答案（非流式）"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': '问题不能为空'}), 400
        
        if len(question) > 1000:
            return jsonify({'error': '问题长度不能超过1000字符'}), 400
        
        # 可选：限制在特定文档内搜索
        document_id = data.get('document_id')
        
        print(f"收到问题: {question}")
        
        # 获取向量存储和RAG服务
        vector_store = get_vector_store(
            current_app.config.get('VECTOR_DB_FOLDER', './vector_db')
        )
        
        rag_service = get_rag_service(
            vector_store,
            current_app.config.get('DEEPSEEK_API_KEY', ''),
            current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')
        )
        
        # 记录开始时间
        start_time = datetime.now()
        
        try:
            # 调用RAG服务获取答案
            answer, sources = rag_service.answer_question(
                question,
                n_context=5,
                document_id=document_id
            )
        except Exception as e:
            # 如果出错（比如没有文档），返回提示信息
            print(f"RAG服务出错: {e}")
            answer = "抱歉，当前知识库中暂无相关文档。请先上传PDF文档后再提问。"
            sources = []
        
        # 计算响应时间
        response_time = (datetime.now() - start_time).total_seconds()
        
        # 保存问答记录
        qa_record = QARecord(
            user_id=DEFAULT_USER_ID,
            question=question,
            answer=answer,
            sources=str(sources),  # 转换为字符串存储
            response_time=response_time
        )
        
        db.session.add(qa_record)
        db.session.commit()
        
        print(f"问答记录已保存: ID={qa_record.id}, 响应时间={response_time:.2f}秒")
        
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


@qa_bp.route('/ask-stream', methods=['POST'])
def ask_question_stream():
    """提问并获取答案（流式输出）- 使用 DeepSeek 推理模型"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': '问题不能为空'}), 400
        
        if len(question) > 1000:
            return jsonify({'error': '问题长度不能超过1000字符'}), 400
        
        # 可选：限制在特定文档内搜索
        document_id = data.get('document_id')
        
        print(f"收到问题（流式）: {question}")
        
        # 获取向量存储和RAG服务
        vector_store = get_vector_store(
            current_app.config.get('VECTOR_DB_FOLDER', './vector_db')
        )
        
        rag_service = get_rag_service(
            vector_store,
            current_app.config.get('DEEPSEEK_API_KEY', ''),
            current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')
        )
        
        # 检索相关上下文
        print("正在检索相关文档...")
        search_results = vector_store.search(
            question, 
            n_results=5,
            document_id=document_id
        )
        
        if not search_results:
            print("⚠️ 未找到相关文档，将使用AI通用知识回答")
            # 没有文档时使用空上下文，AI会基于自己的知识回答
            context = ""
            sources = []
        else:
            print(f"找到 {len(search_results)} 个相关文档片段")
            # 构建上下文
            context = rag_service._build_context(search_results)
            sources = rag_service._format_sources(search_results)
        
        # 构建提示词（无论是否有文档都生成提示词）
        prompt = rag_service._build_prompt(question, context)
        
        # 生成流式响应
        def generate():
            """生成器函数，逐块返回数据"""
            start_time = datetime.now()
            full_answer = []
            full_reasoning = []
            
            try:
                # 首先发送来源信息
                yield f"data: {json.dumps({'type': 'sources', 'data': sources}, ensure_ascii=False)}\n\n"
                
                # 开始流式生成答案
                if rag_service.api_enabled:
                    for chunk_type, chunk_content in rag_service.call_deepseek_stream(prompt):
                        if chunk_type == 'reasoning':
                            # 推理过程
                            full_reasoning.append(chunk_content)
                            yield f"data: {json.dumps({'type': 'reasoning', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                        
                        elif chunk_type == 'content':
                            # 最终答案
                            full_answer.append(chunk_content)
                            yield f"data: {json.dumps({'type': 'content', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                        
                        elif chunk_type == 'error':
                            # 错误信息
                            yield f"data: {json.dumps({'type': 'error', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                            return
                else:
                    # 模拟流式输出
                    answer = rag_service._get_mock_answer(question, search_results)
                    for i in range(0, len(answer), 20):
                        chunk = answer[i:i+20]
                        full_answer.append(chunk)
                        yield f"data: {json.dumps({'type': 'content', 'data': chunk}, ensure_ascii=False)}\n\n"
                        import time
                        time.sleep(0.05)
                
                # 计算响应时间
                response_time = (datetime.now() - start_time).total_seconds()
                answer_text = ''.join(full_answer)
                reasoning_text = ''.join(full_reasoning)
                
                # 保存问答记录
                qa_record = QARecord(
                    user_id=DEFAULT_USER_ID,
                    question=question,
                    answer=answer_text,
                    reasoning=reasoning_text,
                    sources=str(sources),
                    response_time=response_time
                )
                db.session.add(qa_record)
                db.session.commit()
                
                # 发送完成信号
                yield f"data: {json.dumps({'type': 'done', 'data': {'qa_id': qa_record.id, 'response_time': response_time}}, ensure_ascii=False)}\n\n"
                
                print(f"流式问答完成: ID={qa_record.id}, 响应时间={response_time:.2f}秒")
                
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


@qa_bp.route('/history', methods=['GET'])
def get_history():
    """获取问答历史记录"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 查询并分页
        pagination = QARecord.query.filter_by(user_id=DEFAULT_USER_ID)\
            .order_by(QARecord.created_time.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        records = []
        for record in pagination.items:
            records.append({
                'id': record.id,
                'question': record.question,
                'answer': record.answer,
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
        
        # 解析sources
        import ast
        try:
            sources = ast.literal_eval(record.sources) if record.sources else []
        except:
            sources = []
        
        return jsonify({
            'id': record.id,
            'question': record.question,
            'answer': record.answer,
            'sources': sources,
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


@qa_bp.route('/stats', methods=['GET'])
def get_qa_stats():
    """获取问答统计信息"""
    try:
        total_questions = QARecord.query.filter_by(user_id=DEFAULT_USER_ID).count()
        
        # 今日提问数
        from datetime import date
        today = date.today()
        today_questions = QARecord.query.filter_by(user_id=DEFAULT_USER_ID)\
            .filter(db.func.date(QARecord.created_time) == today)\
            .count()
        
        # 平均响应时间
        avg_response_time = db.session.query(db.func.avg(QARecord.response_time))\
            .filter_by(user_id=DEFAULT_USER_ID)\
            .scalar() or 0
        
        # 平均满意度
        avg_satisfaction = db.session.query(db.func.avg(QARecord.satisfaction))\
            .filter_by(user_id=DEFAULT_USER_ID)\
            .filter(QARecord.satisfaction.isnot(None))\
            .scalar() or 0
        
        return jsonify({
            'total_questions': total_questions,
            'today_questions': today_questions,
            'avg_response_time': round(avg_response_time, 2),
            'avg_satisfaction': round(avg_satisfaction, 2)
        })
        
    except Exception as e:
        print(f"获取统计信息时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

