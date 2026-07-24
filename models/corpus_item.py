"""
语料条目数据模型
"""
from . import db
from datetime import datetime


class CorpusItem(db.Model):
    """语料条目表"""
    __tablename__ = 'corpus_items'
    
    id = db.Column(db.Integer, primary_key=True)
    collection_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, default='')
    file_path = db.Column(db.String(500))
    word_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'collection_id': self.collection_id,
            'title': self.title,
            'word_count': self.word_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
