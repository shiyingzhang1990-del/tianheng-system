from . import db
from datetime import datetime


class ChatSession(db.Model):
    """聊天会话表"""
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True, index=True)
    user_id = db.Column(db.Integer, nullable=False, default=1, index=True)
    article_id = db.Column(db.String(50), nullable=False, index=True)
    article_title = db.Column(db.String(500), nullable=True)
    article_content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_messages=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'article_id': self.article_id,
            'article_title': self.article_title,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': ChatMessage.query.filter_by(session_id=self.id).count() if include_messages else 0
        }
        if include_messages:
            messages = ChatMessage.query.filter_by(session_id=self.id).order_by(ChatMessage.created_at).all()
            data['messages'] = [msg.to_dict() for msg in messages]
        return data


class ChatMessage(db.Model):
    """聊天消息表"""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True, index=True)
    session_id = db.Column(db.Integer, nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'question': self.question,
            'answer': self.answer,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
