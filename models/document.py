"""
文档数据模型
"""
from . import db
from datetime import datetime


class Document(db.Model):
    """文档表"""
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, default=1)  # 默认用户ID
    
    # 文档信息
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(100))
    
    # 文件信息
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)  # 字节
    file_hash = db.Column(db.String(64), index=True)  # MD5哈希，用于重复检测
    
    # 内容统计
    page_count = db.Column(db.Integer)
    word_count = db.Column(db.Integer)

    # 文档全文（用于关键词检索）
    full_text = db.Column(db.Text)
    
    # 标签
    tags = db.Column(db.String(500))  # 逗号分隔的标签列表
    
    # 向量化状态
    vector_indexed = db.Column(db.Boolean, default=False)
    
    # 时间戳
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 状态
    status = db.Column(db.String(20), default='active')  # active/deleted
    
    def __repr__(self):
        return f'<Document {self.id}: {self.title}>'
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'page_count': self.page_count,
            'word_count': self.word_count,
            'tags': self.tags.split(',') if self.tags else [],
            'vector_indexed': self.vector_indexed,
            'upload_time': self.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status
        }

