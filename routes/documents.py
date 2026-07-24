"""
文档管理API路由
处理PDF文档的上传、列表、详情、删除等操作
"""
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from models import db
from models.document import Document
from services.pdf_processor import get_pdf_processor
from services.vector_store import get_vector_store

# 创建蓝图
documents_bp = Blueprint('documents', __name__)

# 默认用户ID（无认证模式）
DEFAULT_USER_ID = 1


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@documents_bp.route('/upload', methods=['POST'])
def upload_document():
    """上传PDF文档"""
    try:
        # 检查文件
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': '只支持PDF格式文件'}), 400
        
        # 获取标签（可选）
        tags_str = request.form.get('tags', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]
        
        # 保存文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        print(f"文件已保存: {file_path}")
        
        # 处理PDF
        pdf_processor = get_pdf_processor()
        result = pdf_processor.process_pdf(file_path)
        
        if not result['success']:
            os.remove(file_path)
            return jsonify({'error': f'PDF处理失败: {result.get("error", "未知错误")}'}), 500
        
        # 检查重复（基于文件哈希）
        file_hash = result['metadata']['file_hash']
        existing_doc = Document.query.filter_by(file_hash=file_hash).first()
        
        if existing_doc:
            os.remove(file_path)
            return jsonify({
                'error': '文件已存在',
                'duplicate': True,
                'existing_document': {
                    'id': existing_doc.id,
                    'title': existing_doc.title,
                    'upload_time': existing_doc.upload_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }), 409
        
        # 保存到数据库
        document = Document(
            user_id=DEFAULT_USER_ID,
            title=result['metadata']['title'],
            author=result['metadata']['author'],
            file_path=file_path,
            file_name=filename,
            file_size=os.path.getsize(file_path),
            file_hash=file_hash,
            page_count=result['metadata']['page_count'],
            word_count=result['word_count'],
            tags=','.join(tags) if tags else ''
        )
        
        db.session.add(document)
        db.session.commit()
        
        print(f"文档已保存到数据库: ID={document.id}")
        
        # 向量化并存储
        vector_store = get_vector_store(current_app.config.get('VECTOR_DB_FOLDER', './vector_db'))
        vector_success = vector_store.add_document(
            document_id=document.id,
            chunks=result['chunks'],
            metadata={
                'title': document.title,
                'author': document.author,
                'tags': document.tags
            }
        )
        
        if vector_success:
            document.vector_indexed = True
            db.session.commit()
            print("文档向量化完成")
        
        return jsonify({
            'success': True,
            'message': '文档上传成功',
            'document': {
                'id': document.id,
                'title': document.title,
                'author': document.author,
                'page_count': document.page_count,
                'word_count': document.word_count,
                'tags': tags,
                'upload_time': document.upload_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"上传文档时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/list', methods=['GET'])
def list_documents():
    """获取文档列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        tag = request.args.get('tag', '')
        search = request.args.get('search', '')
        
        # 构建查询
        query = Document.query.filter_by(user_id=DEFAULT_USER_ID)
        
        # 标签筛选
        if tag:
            query = query.filter(Document.tags.contains(tag))
        
        # 搜索过滤
        if search:
            query = query.filter(
                db.or_(
                    Document.title.contains(search),
                    Document.author.contains(search)
                )
            )
        
        # 分页
        pagination = query.order_by(Document.upload_time.desc()).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        documents = []
        for doc in pagination.items:
            documents.append({
                'id': doc.id,
                'title': doc.title,
                'author': doc.author,
                'page_count': doc.page_count,
                'word_count': doc.word_count,
                'file_size': doc.file_size,
                'tags': doc.tags.split(',') if doc.tags else [],
                'upload_time': doc.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
                'vector_indexed': doc.vector_indexed
            })
        
        return jsonify({
            'documents': documents,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        })
        
    except Exception as e:
        print(f"获取文档列表时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    """获取文档详情"""
    try:
        document = Document.query.get(doc_id)
        
        if not document:
            return jsonify({'error': '文档不存在'}), 404
        
        return jsonify({
            'id': document.id,
            'title': document.title,
            'author': document.author,
            'page_count': document.page_count,
            'word_count': document.word_count,
            'file_size': document.file_size,
            'file_name': document.file_name,
            'tags': document.tags.split(',') if document.tags else [],
            'upload_time': document.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'vector_indexed': document.vector_indexed
        })
        
    except Exception as e:
        print(f"获取文档详情时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/<int:doc_id>/download', methods=['GET'])
def download_document(doc_id):
    """下载文档"""
    try:
        document = Document.query.get(doc_id)
        
        if not document:
            return jsonify({'error': '文档不存在'}), 404
        
        if not os.path.exists(document.file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=document.file_name
        )
        
    except Exception as e:
        print(f"下载文档时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档"""
    try:
        document = Document.query.get(doc_id)
        
        if not document:
            return jsonify({'error': '文档不存在'}), 404
        
        # 删除文件
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
            print(f"文件已删除: {document.file_path}")
        
        # 删除向量数据
        vector_store = get_vector_store(current_app.config.get('VECTOR_DB_FOLDER', './vector_db'))
        vector_store.delete_document(doc_id)
        
        # 从数据库删除
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '文档已删除'
        })
        
    except Exception as e:
        print(f"删除文档时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        total_docs = Document.query.filter_by(user_id=DEFAULT_USER_ID).count()
        
        # 标签统计
        all_docs = Document.query.filter_by(user_id=DEFAULT_USER_ID).all()
        tag_counts = {}
        for doc in all_docs:
            if doc.tags:
                for tag in doc.tags.split(','):
                    tag = tag.strip()
                    if tag:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return jsonify({
            'total_documents': total_docs,
            'tag_distribution': tag_counts,
            'total_tags': len(tag_counts)
        })
        
    except Exception as e:
        print(f"获取统计信息时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

