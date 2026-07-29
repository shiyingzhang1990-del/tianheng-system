"""
问答记录数据模型
"""
from . import db
from datetime import datetime


class QARecord(db.Model):
    """问答记录表"""
    __tablename__ = 'qa_records'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, default=1)
    article_id = db.Column(db.Integer, nullable=True, index=True)  # 关联文章ID  # 默认用户ID
    
    # 问答内容
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    reasoning = db.Column(db.Text)  # 推理过程
    sources = db.Column(db.Text)  # JSON字符串，存储引用来源
    
    # 框架信息
    framework = db.Column(db.String(50), default='epic')  # 使用的认知框架ID

    # 性能指标
    response_time = db.Column(db.Float)  # 响应时间（秒）
    
    # 用户反馈
    satisfaction = db.Column(db.Integer)  # 满意度评分（1-5）
    
    # 时间戳
    created_time = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<QARecord {self.id}: {self.question[:50]}...>'
    
    def to_dict(self):
        """转换为字典"""
        import ast
        try:
            sources = ast.literal_eval(self.sources) if self.sources else []
        except:
            sources = []
        
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'reasoning': self.reasoning,
            'sources': sources,
            'response_time': self.response_time,
            'satisfaction': self.satisfaction,
            'created_time': self.created_time.strftime('%Y-%m-%d %H:%M:%S')
        }

