"""
素材数据模型
"""
from . import db
from datetime import datetime


class Material(db.Model):
    """素材表"""
    __tablename__ = 'materials'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    file_type = db.Column(db.String(50))
    content = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'file_type': self.file_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
