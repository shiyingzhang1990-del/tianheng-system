"""
文档管理API路由
处理多格式文档（PDF/DOCX/TXT）的上传、列表、详情、删除等操作
"""
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from models import db
from models.document import Document
from services.file_processor import process_file

documents_bp = Blueprint('documents', __name__)

DEFAULT_USER_ID = 1


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    """从文件名推断文件类型"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext == 'doc':
        return 'docx'
    return ext


@documents_bp.route('/upload', methods=['POST'])
def upload_document():
    """上传文档（PDF/DOCX/TXT）"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': '只支持 PDF、DOCX、TXT 格式文件'}), 400

        tags_str = request.form.get('tags', '')
        tags = [t.strip() for t in tags_str.split(',') if t.strip()]

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        file_type = get_file_type(file.filename)

        # 快速提取文本（使用轻量处理器）
        print(f"开始提取文本: {file_path} (类型: {file_type})")
        text = process_file(file_path, file_type)
        word_count = len(text.replace(' ', '').replace('\n', ''))

        if not text or word_count < 2:
            os.remove(file_path)
            return jsonify({'error': '无法从文件中提取文本内容，请检查文件是否有效'}), 400

        print(f"文本提取完成: {word_count} 字")

        title = os.path.splitext(file.filename)[0]

        document = Document(
            user_id=DEFAULT_USER_ID,
            title=title,
            author='',
            file_path=file_path,
            file_name=filename,
            file_size=os.path.getsize(file_path),
            file_hash='',
            page_count=0,
            word_count=word_count,
            file_type=file_type,
            full_text=text,
            tags=','.join(tags) if tags else ''
        )

        db.session.add(document)
        db.session.commit()

        print(f"文档已保存: ID={document.id}, 类型={file_type}, 字数={word_count}")

        return jsonify({
            'success': True,
            'message': '文档上传成功',
            'document': {
                'id': document.id,
                'title': document.title,
                'author': document.author,
                'file_type': file_type,
                'page_count': document.page_count,
                'word_count': document.word_count,
                'tags': tags,
                'upload_time': document.upload_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except Exception as e:
        print(f"上传文档时出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/list', methods=['GET'])
def list_documents():
    """获取文档列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        tag = request.args.get('tag', '')
        search = request.args.get('search', '')

        query = Document.query.filter_by(user_id=DEFAULT_USER_ID)

        if tag:
            query = query.filter(Document.tags.contains(tag))

        if search:
            query = query.filter(
                db.or_(
                    Document.title.contains(search),
                    Document.author.contains(search)
                )
            )

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
                'file_type': doc.file_type or 'pdf',
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
    """获取文档详情（含全文）"""
    try:
        document = Document.query.get(doc_id)

        if not document:
            return jsonify({'error': '文档不存在'}), 404

        return jsonify({
            'id': document.id,
            'title': document.title,
            'author': document.author,
            'file_type': document.file_type or 'pdf',
            'page_count': document.page_count,
            'word_count': document.word_count,
            'file_size': document.file_size,
            'file_name': document.file_name,
            'tags': document.tags.split(',') if document.tags else [],
            'upload_time': document.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'vector_indexed': document.vector_indexed,
            'full_text': document.full_text or ''
        })

    except Exception as e:
        print(f"获取文档详情时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/<int:doc_id>/content', methods=['GET'])
def get_document_content(doc_id):
    """快速获取文档全文内容（用于阅读）"""
    try:
        document = Document.query.get(doc_id)

        if not document:
            return jsonify({'error': '文档不存在'}), 404

        return jsonify({
            'id': document.id,
            'title': document.title,
            'file_type': document.file_type or 'pdf',
            'word_count': document.word_count,
            'content': document.full_text or '',
            'upload_time': document.upload_time.strftime('%Y-%m-%d %H:%M:%S')
        })

    except Exception as e:
        print(f"获取文档内容时出错: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@documents_bp.route('/<int:doc_id>/download', methods=['GET'])
def download_document(doc_id):
    """下载文档原文件"""
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

        if os.path.exists(document.file_path):
            os.remove(document.file_path)
            print(f"文件已删除: {document.file_path}")

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
