"""
问答API路由
处理智能问答相关的请求
"""
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from datetime import datetime
import json
import requests

from models import db
from models.qa_record import QARecord

qa_bp = Blueprint('qa', __name__)

DEFAULT_USER_ID = 1


def call_deepseek_stream(api_key, api_url, messages):
    """调用 DeepSeek API 流式生成"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'stream': True
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
    """提问并获取答案（流式输出）- 直接使用 DeepSeek API"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        if len(question) > 1000:
            return jsonify({'error': '问题长度不能超过1000字符'}), 400

        api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
        api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com')

        print(f"收到问题（流式）: {question}")

        if not api_key:
            def no_key_generate():
                yield f"data: {json.dumps({'type': 'error', 'data': '请先配置 DeepSeek API Key'}, ensure_ascii=False)}\n\n"
            return Response(
                stream_with_context(no_key_generate()),
                mimetype='text/event-stream'
            )

        messages = [
            {'role': 'system', 'content': '你是一个智能知识助手，请准确、简洁地回答用户的问题。'},
            {'role': 'user', 'content': question}
        ]

        def generate():
            start_time = datetime.now()
            full_answer = []

            try:
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
                        sources='[]',
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
    """提问并获取答案（非流式）"""
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

        print(f"收到问题: {question}")

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': '你是一个智能知识助手，请准确、简洁地回答用户的问题。'},
                {'role': 'user', 'content': question}
            ]
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

        qa_record = QARecord(
            user_id=DEFAULT_USER_ID,
            question=question,
            answer=answer,
            sources='[]',
            response_time=response_time
        )
        db.session.add(qa_record)
        db.session.commit()

        return jsonify({
            'success': True,
            'qa_id': qa_record.id,
            'question': question,
            'answer': answer,
            'sources': [],
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
            'sources': [],
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
