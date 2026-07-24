"""
文章数据模型
"""
from . import db
from datetime import datetime


class Article(db.Model):
    """文章表"""
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, default=1)
    material_id = db.Column(db.Integer, nullable=True)
    analysis_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, default='')
    style = db.Column(db.String(50), default='balanced')
    word_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'style': self.style,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
