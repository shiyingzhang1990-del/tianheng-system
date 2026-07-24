"""
数据模型包
"""
from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例
db = SQLAlchemy()

# 导入所有模型以确保它们被注册
from .user import User
from .document import Document
from .qa_record import QARecord
from .corpus_collection import CorpusCollection
from .corpus_item import CorpusItem
from .material import Material
from .analysis_result import AnalysisResult
from .article import Article
from .chat_history import ChatSession, ChatMessage

__all__ = ['db', 'User', 'Document', 'QARecord', 'CorpusCollection', 'CorpusItem',
           'Material', 'AnalysisResult', 'Article', 'ChatSession', 'ChatMessage']
