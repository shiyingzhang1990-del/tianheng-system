from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import json
import time
from models import db, Material, AnalysisResult, Article, QARecord
from services.ai_generator import generate_article, generate_qa_response, generate_article_stream

articles_bp = Blueprint('articles', __name__)

# 默认用户ID（移除认证后使用）
DEFAULT_USER_ID = 1

@articles_bp.route('/generate', methods=['POST'])
def generate_article_route():
    current_user_id = DEFAULT_USER_ID
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    material_id = data.get('materialId')
    analysis_id = data.get('analysisId')
    selected_logic = data.get('selectedLogic')
    style_preference = data.get('stylePreference', 'balanced')
    word_count = data.get('wordCount', 1000)
    custom_style = data.get('customStyle')
    use_corpus = data.get('useCorpus', False)
    custom_instructions = data.get('customInstructions')
    logic_structures = data.get('logicStructures')
    
    # 验证必要参数
    if not material_id:
        return jsonify({'error': 'Material ID is required'}), 400
    
    # 获取素材
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    # 获取分析结果
    analysis = AnalysisResult.query.filter_by(material_id=material_id).order_by(AnalysisResult.created_at.desc()).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found for this material'}), 404
    
    # 解析分析结果
    keywords = json.loads(analysis.keywords)
    opinions = json.loads(analysis.opinions)
    logic_structure = json.loads(analysis.logic_structure)
    
    # 生成文章
    article_content = generate_article(
        keywords=keywords,
        opinions=opinions,
        logic_structure=logic_structure,
        selected_logic=selected_logic,
        style_preference=style_preference,
        word_count=word_count,
        custom_style=custom_style,
        use_corpus=use_corpus,
        custom_instructions=custom_instructions,
        logic_structures=logic_structures
    )
    
    # 保存文章
    article = Article(
        user_id=current_user_id,
        material_id=material_id,
        analysis_id=analysis.id,
        title=f"基于《{material.title}》的文章",
        content=article_content,
        style=style_preference
    )
    
    db.session.add(article)
    db.session.commit()
    
    return jsonify({
        'message': 'Article generated successfully',
        'article': {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'created_at': article.created_at.isoformat()
        }
    }), 201

@articles_bp.route('/generate-stream', methods=['POST'])
def generate_article_stream_route():
    current_user_id = DEFAULT_USER_ID
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    material_id = data.get('materialId')
    analysis_id = data.get('analysisId')
    selected_logic = data.get('selectedLogic')
    style_preference = data.get('stylePreference', 'balanced')
    word_count = data.get('wordCount', 1000)
    custom_style = data.get('customStyle')
    use_corpus = data.get('useCorpus', False)
    custom_instructions = data.get('customInstructions')
    logic_structures = data.get('logicStructures')
    
    # 验证必要参数
    if not material_id:
        return jsonify({'error': 'Material ID is required'}), 400
    
    # 获取素材
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    # 获取分析结果
    analysis = AnalysisResult.query.filter_by(material_id=material_id).order_by(AnalysisResult.created_at.desc()).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found for this material'}), 404
    
    # 解析分析结果
    keywords = json.loads(analysis.keywords)
    opinions = json.loads(analysis.opinions)
    logic_structure = json.loads(analysis.logic_structure)
    
    def generate_stream():
        try:
            # 发送开始信号
            yield f"data: {json.dumps({'type': 'start', 'message': '开始生成文章...'})}\n\n"
            
            # 创建文章记录
            article = Article(
                user_id=current_user_id,
                material_id=material_id,
                analysis_id=analysis.id,
                title='生成中...',
                content='',
                style=style_preference,
                word_count=word_count
            )
            db.session.add(article)
            db.session.commit()
            
            # 发送文章ID
            yield f"data: {json.dumps({'type': 'article_id', 'article_id': article.id})}\n\n"
            
            # 流式生成文章内容
            for chunk in generate_article_stream(
                keywords=keywords,
                opinions=opinions,
                logic_structure=logic_structure,
                selected_logic=selected_logic,
                style_preference=style_preference,
                word_count=word_count,
                custom_style=custom_style,
                use_corpus=use_corpus,
                custom_instructions=custom_instructions,
                logic_structures=logic_structures
            ):
                # 更新文章内容
                article.content += chunk
                db.session.commit()
                
                # 发送内容块
                yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            
            # 生成完成，更新文章标题
            if article.content:
                # 提取标题（第一行或前50个字符）
                lines = article.content.split('\n')
                title = lines[0].replace('#', '').strip() if lines[0].startswith('#') else lines[0][:50]
                article.title = title if title else '生成的文章'
                db.session.commit()
            
            # 发送完成信号
            yield f"data: {json.dumps({'type': 'complete', 'message': '文章生成完成'})}\n\n"
            
        except Exception as e:
            current_app.logger.error(f"Stream generation error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )

@articles_bp.route('', methods=['GET'])
def get_articles():
    current_user_id = DEFAULT_USER_ID
    
    articles = Article.query.filter_by(user_id=current_user_id).order_by(Article.created_at.desc()).all()
    
    return jsonify({
        'articles': [{
            'id': article.id,
            'title': article.title,
            'created_at': article.created_at.isoformat()
        } for article in articles]
    }), 200

@articles_bp.route('/<int:article_id>', methods=['GET'])
def get_article(article_id):
    current_user_id = DEFAULT_USER_ID
    
    article = Article.query.filter_by(id=article_id, user_id=current_user_id).first()
    
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    
    return jsonify({
        'article': {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'style': article.style,
            'created_at': article.created_at.isoformat()
        }
    }), 200

@articles_bp.route('/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    current_user_id = DEFAULT_USER_ID
    
    article = Article.query.filter_by(id=article_id, user_id=current_user_id).first()
    
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    
    data = request.json
    
    if 'title' in data:
        article.title = data['title']
    
    if 'content' in data:
        article.content = data['content']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Article updated successfully',
        'article': {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'created_at': article.created_at.isoformat()
        }
    }), 200

@articles_bp.route('/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    current_user_id = DEFAULT_USER_ID
    
    article = Article.query.filter_by(id=article_id, user_id=current_user_id).first()
    
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    
    # 删除相关的问答记录
    QARecord.query.filter_by(article_id=article_id).delete()
    
    # 删除文章
    db.session.delete(article)
    db.session.commit()
    
    return jsonify({'message': 'Article deleted successfully'}), 200

@articles_bp.route('/<int:article_id>/qa', methods=['POST'])
def submit_question(article_id):
    current_user_id = DEFAULT_USER_ID
    
    article = Article.query.filter_by(id=article_id, user_id=current_user_id).first()
    
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    
    data = request.json
    
    if not data or 'question' not in data:
        return jsonify({'error': 'Question is required'}), 400
    
    question = data['question']
    
    # 生成回答
    answer = generate_qa_response(article.content, question)
    
    # 保存问答记录
    qa_record = QARecord(
        user_id=current_user_id,
        article_id=article_id,
        question=question,
        answer=answer
    )
    
    db.session.add(qa_record)
    db.session.commit()
    
    return jsonify({
        'message': 'Question answered successfully',
        'qa': {
            'id': qa_record.id,
            'question': qa_record.question,
            'answer': qa_record.answer,
            'created_at': qa_record.created_at.isoformat()
        }
    }), 201

@articles_bp.route('/<int:article_id>/qa', methods=['GET'])
def get_qa_history(article_id):
    current_user_id = DEFAULT_USER_ID
    
    article = Article.query.filter_by(id=article_id, user_id=current_user_id).first()
    
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    
    qa_records = QARecord.query.filter_by(article_id=article_id).order_by(QARecord.created_at).all()
    
    return jsonify({
        'qa_history': [{
            'id': record.id,
            'question': record.question,
            'answer': record.answer,
            'created_at': record.created_at.isoformat()
        } for record in qa_records]
    }), 200