from flask import Blueprint, request, jsonify, current_app
import os
import json
from models import db, CorpusCollection, CorpusItem
from services.corpus_analyzer import analyze_corpus

corpus_bp = Blueprint('corpus', __name__)

# 默认用户ID（移除认证后使用）
DEFAULT_USER_ID = 1

@corpus_bp.route('/collections', methods=['POST'])
def create_collection():
    current_user_id = DEFAULT_USER_ID
    data = request.get_json()
    
    if 'name' not in data:
        return jsonify({'error': 'Collection name is required'}), 400
    
    collection = CorpusCollection(
        user_id=current_user_id,
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
    current_user_id = DEFAULT_USER_ID
    
    collections = CorpusCollection.query.filter_by(user_id=current_user_id).all()
    
    return jsonify({
        'collections': [collection.to_dict() for collection in collections]
    }), 200

@corpus_bp.route('/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    return jsonify({
        'collection': collection.to_dict()
    }), 200

@corpus_bp.route('/collections/<int:collection_id>', methods=['PUT'])
def update_collection(collection_id):
    current_user_id = DEFAULT_USER_ID
    data = request.get_json()
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
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
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    # 删除相关的语料项
    CorpusItem.query.filter_by(collection_id=collection_id).delete()
    
    # 删除集合
    db.session.delete(collection)
    db.session.commit()
    
    return jsonify({'message': 'Collection deleted successfully'}), 200

@corpus_bp.route('/collections/<int:collection_id>/items', methods=['POST'])
def add_corpus_item(collection_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    data = request.get_json()
    
    if 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Title and content are required'}), 400
    
    # 创建语料项（纯文本版本）
    corpus_item = CorpusItem(
        collection_id=collection_id,
        title=data['title'],
        content=data['content'],
        word_count=len(data['content'])
    )
    
    db.session.add(corpus_item)
    db.session.commit()
    
    return jsonify({
        'message': 'Corpus item added successfully',
        'item': corpus_item.to_dict()
    }), 201

@corpus_bp.route('/collections/<int:collection_id>/items', methods=['GET'])
def get_corpus_items(collection_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    items = CorpusItem.query.filter_by(collection_id=collection_id).all()
    
    return jsonify({
        'items': [item.to_dict() for item in items]
    }), 200

@corpus_bp.route('/collections/<int:collection_id>/items/<int:item_id>', methods=['GET'])
def get_corpus_item(collection_id, item_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    item = CorpusItem.query.filter_by(id=item_id, collection_id=collection_id).first()
    
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    
    return jsonify({
        'item': item.to_dict(include_content=True)
    }), 200

@corpus_bp.route('/collections/<int:collection_id>/items/<int:item_id>', methods=['DELETE'])
def delete_corpus_item(collection_id, item_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    item = CorpusItem.query.filter_by(id=item_id, collection_id=collection_id).first()
    
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'message': 'Item deleted successfully'}), 200

@corpus_bp.route('/collections/<int:collection_id>/analyze', methods=['GET'])
def analyze_collection(collection_id):
    current_user_id = DEFAULT_USER_ID
    
    collection = CorpusCollection.query.filter_by(id=collection_id, user_id=current_user_id).first()
    
    if not collection:
        return jsonify({'error': 'Collection not found'}), 404
    
    items = CorpusItem.query.filter_by(collection_id=collection_id).all()
    
    if not items:
        return jsonify({'error': 'No items in collection'}), 404
    
    # 合并所有语料项的内容
    combined_content = "\n\n".join([item.content for item in items if item.content])
    
    if not combined_content:
        return jsonify({'error': 'No content to analyze'}), 400
    
    # 分析语料库
    analysis_result = analyze_corpus(combined_content)
    
    return jsonify({
        'analysis': analysis_result
    }), 200
