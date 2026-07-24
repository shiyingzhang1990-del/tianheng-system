from flask import Blueprint, request, jsonify, current_app
from models import db, ChatSession, ChatMessage, User
from sqlalchemy import desc
from datetime import datetime
from services.ai_generator import generate_qa_response

chat_history_bp = Blueprint('chat_history', __name__)

# 默认用户ID（移除认证后使用）
DEFAULT_USER_ID = 1


@chat_history_bp.route('/sessions', methods=['POST'])
def create_or_get_session():
    """创建或获取聊天会话"""
    try:
        user_id = DEFAULT_USER_ID
        data = request.get_json()
        
        article_id = data.get('article_id')
        article_title = data.get('article_title', '')
        article_content = data.get('article_content', '')
        is_temp = data.get('is_temp', False)  # 是否为临时会话，默认为否
        
        if not article_id:
            return jsonify({
                'success': False,
                'message': '缺少文章ID'
            }), 400
        
        # 查找或创建会话
        session = ChatSession.query.filter_by(
            user_id=user_id,
            article_id=str(article_id)
        ).first()
        
        if not session:
            # 如果是临时会话，则不实际创建数据库记录，只返回一个临时对象
            if is_temp:
                temp_session = {
                    'id': 0,  # 临时ID
                    'user_id': user_id,
                    'article_id': str(article_id),
                    'article_title': article_title,
                    'article_content': article_content,
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat(),
                    'message_count': 0,
                    'is_temp': True  # 标记为临时会话
                }
                return jsonify({
                    'success': True,
                    'data': temp_session
                })
            else:
                # 正常创建会话
                session = ChatSession(
                    user_id=user_id,
                    article_id=str(article_id),
                    article_title=article_title,
                    article_content=article_content
                )
                db.session.add(session)
                db.session.commit()
        else:
            # 更新文章标题和内容（如果提供）
            if article_title:
                session.article_title = article_title
            if article_content:
                session.article_content = article_content
            session.updated_at = datetime.utcnow()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'data': session.to_dict(include_messages=True)
        })
        
    except Exception as e:
        current_app.logger.error(f"创建会话失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'创建会话失败: {str(e)}'
        }), 500


@chat_history_bp.route('/sessions/<session_id>/ask', methods=['POST'])
def ask_question(session_id):
    """向AI提问并获取回答"""
    try:
        user_id = DEFAULT_USER_ID
        data = request.get_json()
        
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({
                'success': False,
                'message': '问题不能为空'
            }), 400
        
        # 验证会话所有权
        session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not session:
            return jsonify({
                'success': False,
                'message': '会话不存在或无权限'
            }), 404
        
        # 获取会话的历史消息（最近10条，按时间顺序）
        history_messages = ChatMessage.query.filter_by(session_id=session_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(10)\
            .all()
        
        # 转换为时间正序（最早的在前）
        history_messages.reverse()
        
        # 调用AI服务生成回答，传入历史对话上下文
        answer = generate_qa_response(
            session.article_content or '', 
            question, 
            history_messages
        )
        
        if not answer:
            return jsonify({
                'success': False,
                'message': 'AI服务暂时不可用'
            }), 500
        
        # 创建消息
        message = ChatMessage(
            session_id=session_id,
            question=question,
            answer=answer
        )
        
        db.session.add(message)
        
        # 更新会话时间
        session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': message.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"AI问答失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'AI问答失败: {str(e)}'
        }), 500


@chat_history_bp.route('/sessions/<session_id>/messages', methods=['POST'])
def add_message(session_id):
    """添加聊天消息（手动指定答案）"""
    try:
        user_id = DEFAULT_USER_ID
        data = request.get_json()
        
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        
        if not question or not answer:
            return jsonify({
                'success': False,
                'message': '问题和答案不能为空'
            }), 400
        
        # 验证会话所有权
        session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not session:
            return jsonify({
                'success': False,
                'message': '会话不存在或无权限'
            }), 404
        
        # 创建消息
        message = ChatMessage(
            session_id=session_id,
            question=question,
            answer=answer
        )
        
        db.session.add(message)
        
        # 更新会话时间
        session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': message.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"添加消息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'添加消息失败: {str(e)}'
        }), 500


@chat_history_bp.route('/sessions/<article_id>', methods=['GET'])
def get_session_by_article(article_id):
    """根据文章ID获取会话和消息历史"""
    try:
        user_id = DEFAULT_USER_ID
        
        session = ChatSession.query.filter_by(
            user_id=user_id,
            article_id=str(article_id)
        ).first()
        
        if not session:
            return jsonify({
                'success': True,
                'data': {
                    'session': None,
                    'messages': []
                }
            })
        
        return jsonify({
            'success': True,
            'data': {
                'session': session.to_dict(),
                'messages': [msg.to_dict() for msg in session.chat_messages.order_by(ChatMessage.created_at)]
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"获取会话失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取会话失败: {str(e)}'
        }), 500


@chat_history_bp.route('/sessions', methods=['GET'])
def get_user_sessions():
    """获取用户的所有聊天会话列表"""
    try:
        user_id = DEFAULT_USER_ID
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        sessions = ChatSession.query.filter_by(user_id=user_id)\
            .order_by(desc(ChatSession.updated_at))\
            .paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
        
        return jsonify({
            'success': True,
            'data': {
                'sessions': [session.to_dict() for session in sessions.items],
                'pagination': {
                    'total': sessions.total,
                    'pages': sessions.pages,
                    'current_page': sessions.page,
                    'per_page': sessions.per_page,
                    'has_next': sessions.has_next,
                    'has_prev': sessions.has_prev
                }
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"获取会话列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取会话列表失败: {str(e)}'
        }), 500


@chat_history_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除聊天会话及其所有消息"""
    try:
        user_id = DEFAULT_USER_ID
        
        session = ChatSession.query.filter_by(
            id=session_id,
            user_id=user_id
        ).first()
        
        if not session:
            return jsonify({
                'success': False,
                'message': '会话不存在或无权限'
            }), 404
        
        db.session.delete(session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '会话删除成功'
        })
        
    except Exception as e:
        current_app.logger.error(f"删除会话失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除会话失败: {str(e)}'
        }), 500


@chat_history_bp.route('/messages/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    """删除单条聊天消息"""
    try:
        user_id = DEFAULT_USER_ID
        
        # 通过会话验证用户权限
        message = ChatMessage.query.join(ChatSession)\
            .filter(
                ChatMessage.id == message_id,
                ChatSession.user_id == user_id
            ).first()
        
        if not message:
            return jsonify({
                'success': False,
                'message': '消息不存在或无权限'
            }), 404
        
        db.session.delete(message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '消息删除成功'
        })
        
    except Exception as e:
        current_app.logger.error(f"删除消息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除消息失败: {str(e)}'
        }), 500
