"""
分析结果数据模型
"""
from . import db
from datetime import datetime


class AnalysisResult(db.Model):
    """分析结果表"""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, nullable=False, index=True)
    keywords = db.Column(db.Text, default='[]')
    opinions = db.Column(db.Text, default='[]')
    logic_structure = db.Column(db.Text, default='[]')
    summary = db.Column(db.Text, default='')
    logic_structures = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
