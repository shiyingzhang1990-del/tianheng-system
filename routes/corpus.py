from flask import Blueprint, request, jsonify, current_app
import os
from werkzeug.utils import secure_filename
from models import db, CorpusCollection, CorpusItem
from services.file_processor import process_file
from services.corpus_analyzer import analyze_corpus
from utils.file_utils import safe_filename, get_file_extension

corpus_bp = Blueprint('corpus', __name__)

# 默认用户ID（移除认证后使用）
DEFAULT_USER_ID = 1


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'pdf'})


@corpus_bp.route('/collections', methods=['POST'])
def create_collection():
    data = request.get_json()
    
    if 'name' not in data:
        return jsonify({'error': 'Collection name is required'}), 400
    
    collection = CorpusCollection(
        user_id=DEFAULT_USER_ID,
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(collection)
    db.session.commit()
    
    return jsonify({
        'message': 'Collection created successfully',
        'collection': collection.to_dict()
    }), 201


@corpus_bp.route('/collections', methods=['GET'])
def get_collections():
    collections = CorpusCollection.query.filter_by(user_id=DEFAULT_USER_ID).all()
    return jsonify({
        'collections': [collection.to_dict() for collection in collections]
    }), 200


@corpus_bp.route('/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    return jsonify({'collection': collection.to_dict()}), 200


@corpus_bp.route('/collections/<int:collection_id>', methods=['PUT'])
def update_collection(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        collection.name = data['name']
    if 'description' in data:
        collection.description = data['description']
    db.session.commit()
    
    return jsonify({
        'message': 'Collection updated successfully',
        'collection': collection.to_dict()
    }), 200


@corpus_bp.route('/collections/<int:collection_id>', methods=['DELETE'])
def delete_collection(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    items = CorpusItem.query.filter_by(collection_id=collection_id).all()
    for item in items:
        try:
            if item.file_path and os.path.exists(item.file_path):
                os.remove(item.file_path)
        except Exception as e:
            current_app.logger.error(f"Error deleting file: {e}")
    CorpusItem.query.filter_by(collection_id=collection_id).delete()
    db.session.delete(collection)
    db.session.commit()
    
    return jsonify({'message': 'Collection deleted successfully'}), 200


@corpus_bp.route('/collections/<int:collection_id>/items', methods=['POST'])
def add_corpus_item(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    original_filename = file.filename
    filename = safe_filename(original_filename, "corpus")
    corpus_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', './uploads'), 'corpus')
    file_path = os.path.join(corpus_dir, filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file.save(file_path)
    
    title = request.form.get('title', original_filename)
    file_type = get_file_extension(original_filename)
    content = process_file(file_path, file_type)
    word_count = len(content)
    
    corpus_item = CorpusItem(
        collection_id=collection_id,
        title=title,
        content=content,
        file_path=file_path,
        word_count=word_count
    )
    db.session.add(corpus_item)
    db.session.commit()
    
    return jsonify({
        'message': 'Corpus item added successfully',
        'item': corpus_item.to_dict()
    }), 201


@corpus_bp.route('/collections/<int:collection_id>/items', methods=['GET'])
def get_corpus_items(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    items = CorpusItem.query.filter_by(collection_id=collection_id).all()
    return jsonify({'items': [item.to_dict() for item in items]}), 200


@corpus_bp.route('/collections/<int:collection_id>/items/<int:item_id>', methods=['GET'])
def get_corpus_item(collection_id, item_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    item = CorpusItem.query.filter_by(id=item_id, collection_id=collection_id).first()
    if not item:
        return jsonify({'error': 'Corpus item not found'}), 404
    return jsonify({'item': {**item.to_dict(), 'content': item.content}}), 200


@corpus_bp.route('/collections/<int:collection_id>/items/<int:item_id>', methods=['PUT'])
def update_corpus_item(collection_id, item_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    item = CorpusItem.query.filter_by(id=item_id, collection_id=collection_id).first()
    if not item:
        return jsonify({'error': 'Corpus item not found'}), 404
    data = request.get_json()
    if 'title' in data:
        item.title = data['title']
    if 'content' in data:
        item.content = data['content']
        item.word_count = len(data['content'])
    db.session.commit()
    return jsonify({'message': 'Corpus item updated successfully', 'item': item.to_dict()}), 200


@corpus_bp.route('/collections/<int:collection_id>/items/<int:item_id>', methods=['DELETE'])
def delete_corpus_item(collection_id, item_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    item = CorpusItem.query.filter_by(id=item_id, collection_id=collection_id).first()
    if not item:
        return jsonify({'error': 'Corpus item not found'}), 404
    try:
        if item.file_path and os.path.exists(item.file_path):
            os.remove(item.file_path)
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Corpus item deleted successfully'}), 200


@corpus_bp.route('/collections/<int:collection_id>/analyze', methods=['GET'])
def analyze_collection(collection_id):
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=DEFAULT_USER_ID).first()
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    items = CorpusItem.query.filter_by(collection_id=collection_id).all()
    if not items:
        return jsonify({'error': 'No corpus items found in this collection'}), 400
    corpus_content = ' '.join([item.content for item in items])
    analysis_result = analyze_corpus(corpus_content)
    return jsonify({'analysis': analysis_result}), 200
