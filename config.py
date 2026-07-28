import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _get_api_key():
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not key or key.startswith('请填写'):
        return ''
    return key


class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tianheng-secret-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'tianheng-secret-2024'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=90)

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

    # DeepSeek AI模型配置
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL') or 'https://api.deepseek.com'
    DEEPSEEK_API_KEY = _get_api_key()

    # 向量数据库配置
    VECTOR_DB_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vector_db')

    # 默认登录密码
    DEFAULT_USERNAME = os.environ.get('DEFAULT_USERNAME') or 'admin'
    DEFAULT_PASSWORD = os.environ.get('DEFAULT_PASSWORD') or 'admin123'


class DevelopmentConfig(Config):
    DEBUG = True
    DEEPSEEK_API_KEY = _get_api_key()
    DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL') or 'https://api.deepseek.com'


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
