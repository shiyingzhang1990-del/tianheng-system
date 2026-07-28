from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import os

from config import DevelopmentConfig
from models import db
from routes.documents import documents_bp
from routes.qa import qa_bp
from routes.export import export_bp
from routes.license import license_bp
from routes.auth import auth_bp, ensure_default_user
from routes.chat_history import chat_history_bp
from routes.corpus import corpus_bp
from routes.materials import materials_bp
from routes.articles import articles_bp

os.environ["FLASK_SKIP_DOTENV"] = "1"


def create_app(config_class=DevelopmentConfig):
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    
    app = Flask(__name__, 
                static_folder=static_folder,
                static_url_path='')
    app.config.from_object(config_class)
    
    db.init_app(app)
    CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})
    
    # Register all blueprints
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(qa_bp, url_prefix='/api/qa')
    app.register_blueprint(export_bp, url_prefix='/api/export')
    app.register_blueprint(license_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(corpus_bp, url_prefix='/api/corpus')
    app.register_blueprint(materials_bp, url_prefix='/api/materials')
    app.register_blueprint(articles_bp, url_prefix='/api/articles')
    app.register_blueprint(chat_history_bp, url_prefix='/api/chat')
    
    @app.route('/')
    def index():
        return send_from_directory(static_folder, 'index.html')
    
    @app.route('/<path:path>')
    def serve_static(path):
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404
        file_path = os.path.join(static_folder, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(static_folder, path)
        return send_from_directory(static_folder, 'index.html')
    
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return send_from_directory(static_folder, 'index.html')
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            'error': '文件太大',
            'details': '文件大小超过服务器限制，请联系管理员调整配置'
        }), 413
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    with app.app_context():
        db.create_all()
        # 迁移：为已有数据库添加 full_text 列和 file_type 列
        try:
            from sqlalchemy import text
            db.session.execute(text('ALTER TABLE documents ADD COLUMN full_text TEXT'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        try:
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE documents ADD COLUMN file_type VARCHAR(10) DEFAULT 'pdf'"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # 将所有已有文档标记为已就绪（不再使用向量索引）
        try:
            from sqlalchemy import text
            db.session.execute(text("UPDATE documents SET vector_indexed = 1 WHERE vector_indexed = 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        ensure_default_user()
    
    return app


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app = create_app()
    print("=" * 60)
    print(" 天衡系统 v2.0 - 智能知识助手")
    print("=" * 60)
    print(f" 访问地址: http://localhost:{port}")
    print(" 默认登录: admin / admin123")
    print(" (可在环境变量 DEFAULT_USERNAME / DEFAULT_PASSWORD 中修改)")
    print("=" * 60)
    app.run(debug=debug, host='::', port=port)
