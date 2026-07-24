from flask import Blueprint, request, jsonify, current_app
import os
import json
from werkzeug.utils import secure_filename
from models import db, Material, AnalysisResult
from services.file_processor import process_file
from services.ai_analyzer import analyze_material
from utils.file_utils import safe_filename, get_file_extension

materials_bp = Blueprint('materials', __name__)

# 默认用户ID（移除认证后使用）
DEFAULT_USER_ID = 1

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@materials_bp.route('', methods=['POST'])
def upload_material():
    current_user_id = DEFAULT_USER_ID
    
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # 检查文件名
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # 使用工具函数处理文件名
    original_filename = file.filename
    filename = safe_filename(original_filename, "upload")
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    # 确保上传目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    file.save(file_path)
    
    # 处理文件内容
    title = request.form.get('title', original_filename)  # 使用原始文件名作为标题
    
    # 从原始文件名获取文件类型
    file_type = get_file_extension(original_filename)
    
    # 处理文件内容（移除严格验证，无论如何都尝试解析）
    content = process_file(file_path, file_type)
    
    # 只有在完全无法处理时才返回错误
    if content.startswith("python-docx库未安装"):
        # 删除文件
        try:
            os.remove(file_path)
        except:
            pass
        return jsonify({
            'error': '系统错误',
            'details': 'Word文档处理库未安装，请联系管理员'
        }), 500
    
    # 创建素材记录
    material = Material(
        user_id=current_user_id,
        title=title,
        file_path=file_path,
        file_type=file_type,
        content=content
    )
    
    db.session.add(material)
    db.session.commit()
    
    return jsonify({
        'message': 'Material uploaded successfully',
        'material': material.to_dict()
    }), 201

@materials_bp.route('', methods=['GET'])
def get_materials():
    current_user_id = DEFAULT_USER_ID
    
    materials = Material.query.filter_by(user_id=current_user_id).order_by(Material.created_at.desc()).all()
    
    return jsonify({
        'materials': [material.to_dict() for material in materials]
    }), 200

@materials_bp.route('/<int:material_id>', methods=['GET'])
def get_material(material_id):
    current_user_id = DEFAULT_USER_ID
    
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    return jsonify({
        'material': {
            **material.to_dict(),
            'content': material.content
        }
    }), 200

@materials_bp.route('/analyze-session', methods=['POST'])
def analyze_session_materials():
    """分析指定的素材（当前会话）"""
    current_user_id = DEFAULT_USER_ID
    
    # 获取请求中的素材ID列表
    data = request.get_json()
    material_ids = data.get('material_ids', [])
    
    if not material_ids:
        return jsonify({'error': 'No material IDs provided'}), 400
    
    # 获取指定的素材
    materials = Material.query.filter(
        Material.id.in_(material_ids),
        Material.user_id == current_user_id
    ).all()
    
    if not materials:
        return jsonify({'error': 'No materials found'}), 404
    
    # 合并指定素材的内容
    combined_content = ""
    material_info = []
    
    for material in materials:
        if material.content:
            # 添加文件标识和内容
            combined_content += f"\n\n=== 文件：{material.title} ===\n"
            combined_content += material.content
            material_info.append({
                'id': material.id,
                'title': material.title,
                'file_type': material.file_type
            })
    
    if not combined_content.strip():
        return jsonify({'error': 'No content to analyze'}), 400
    
    current_app.logger.info(f"Analyzing session content from {len(materials)} materials, total length: {len(combined_content)}")
    
    # 分析合并后的内容
    analysis_result = analyze_material(combined_content)
    current_app.logger.info(f"Analysis result keys: {list(analysis_result.keys()) if analysis_result else 'None'}")
    
    # 选择最新的素材作为主要素材来保存分析结果
    primary_material = materials[-1]  # 使用最后一个素材
    
    # 保存分析结果
    result = AnalysisResult(
        material_id=primary_material.id,
        keywords=json.dumps(analysis_result.get('keywords', [])),
        opinions=json.dumps(analysis_result.get('opinions', [])),
        logic_structure=json.dumps(analysis_result.get('logic_structure', [])),
        summary=analysis_result.get('summary', ''),
        logic_structures=json.dumps(analysis_result.get('logic_structures', []))
    )
    
    db.session.add(result)
    db.session.commit()
    
    return jsonify({
        'message': 'Session materials analyzed successfully',
        'analyzed_materials': material_info,
        'primary_material_id': primary_material.id,
        'analysis': {
            'id': result.id,
            'keywords': analysis_result.get('keywords', []),
            'opinions': analysis_result.get('opinions', []),
            'logic_structure': analysis_result.get('logic_structure', []),
            'summary': analysis_result.get('summary', ''),
            'logic_structures': analysis_result.get('logic_structures', [])
        }
    }), 200

@materials_bp.route('/analyze-all', methods=['POST'])
def analyze_all_materials():
    """分析用户的所有素材（合并分析）"""
    current_user_id = DEFAULT_USER_ID
    
    # 获取用户的所有素材
    materials = Material.query.filter_by(user_id=current_user_id).all()
    
    if not materials:
        return jsonify({'error': 'No materials found'}), 404
    
    # 合并所有素材的内容
    combined_content = ""
    material_info = []
    
    for material in materials:
        if material.content:
            # 添加文件标识和内容
            combined_content += f"\n\n=== 文件：{material.title} ===\n"
            combined_content += material.content
            material_info.append({
                'id': material.id,
                'title': material.title,
                'file_type': material.file_type
            })
    
    if not combined_content.strip():
        return jsonify({'error': 'No content to analyze'}), 400
    
    current_app.logger.info(f"Analyzing combined content from {len(materials)} materials, total length: {len(combined_content)}")
    
    # 分析合并后的内容
    analysis_result = analyze_material(combined_content)
    current_app.logger.info(f"Analysis result keys: {list(analysis_result.keys()) if analysis_result else 'None'}")
    
    # 选择最新的素材作为主要素材来保存分析结果
    primary_material = materials[-1]  # 使用最后上传的素材
    
    # 保存分析结果
    result = AnalysisResult(
        material_id=primary_material.id,
        keywords=json.dumps(analysis_result.get('keywords', [])),
        opinions=json.dumps(analysis_result.get('opinions', [])),
        logic_structure=json.dumps(analysis_result.get('logic_structure', [])),
        summary=analysis_result.get('summary', ''),
        logic_structures=json.dumps(analysis_result.get('logic_structures', []))
    )
    
    db.session.add(result)
    db.session.commit()
    
    return jsonify({
        'message': 'All materials analyzed successfully',
        'analyzed_materials': material_info,
        'primary_material_id': primary_material.id,
        'analysis': {
            'id': result.id,
            'keywords': analysis_result.get('keywords', []),
            'opinions': analysis_result.get('opinions', []),
            'logic_structure': analysis_result.get('logic_structure', []),
            'summary': analysis_result.get('summary', ''),
            'logic_structures': analysis_result.get('logic_structures', [])
        }
    }), 200

@materials_bp.route('/<int:material_id>/analyze', methods=['POST'])
def analyze_material_content(material_id):
    """分析单个素材（保留向后兼容性）"""
    current_user_id = DEFAULT_USER_ID
    
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    # 分析素材
    analysis_result = analyze_material(material.content)
    current_app.logger.info(f"Analysis result keys: {list(analysis_result.keys()) if analysis_result else 'None'}")
    
    # 保存分析结果
    result = AnalysisResult(
        material_id=material.id,
        keywords=json.dumps(analysis_result.get('keywords', [])),
        opinions=json.dumps(analysis_result.get('opinions', [])),
        logic_structure=json.dumps(analysis_result.get('logic_structure', [])),
        summary=analysis_result.get('summary', ''),
        logic_structures=json.dumps(analysis_result.get('logic_structures', []))
    )
    
    db.session.add(result)
    db.session.commit()
    
    return jsonify({
        'message': 'Material analyzed successfully',
        'analysis': {
            'id': result.id,
            'keywords': analysis_result.get('keywords', []),
            'opinions': analysis_result.get('opinions', []),
            'logic_structure': analysis_result.get('logic_structure', []),
            'summary': analysis_result.get('summary', ''),
            'logic_structures': analysis_result.get('logic_structures', [])
        }
    }), 200

@materials_bp.route('/<int:material_id>/analysis', methods=['GET'])
def get_analysis_result(material_id):
    current_user_id = DEFAULT_USER_ID
    
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    analysis = AnalysisResult.query.filter_by(material_id=material_id).order_by(AnalysisResult.created_at.desc()).first()
    
    if not analysis:
        return jsonify({'error': 'No analysis found for this material'}), 404
    
    return jsonify({
        'analysis': {
            'id': analysis.id,
            'keywords': json.loads(analysis.keywords),
            'opinions': json.loads(analysis.opinions),
            'logic_structure': json.loads(analysis.logic_structure),
            'summary': getattr(analysis, 'summary', '') or '',
            'logic_structures': json.loads(getattr(analysis, 'logic_structures', '') or '[]'),
            'created_at': analysis.created_at.isoformat()
        }
    }), 200

@materials_bp.route('/<int:material_id>', methods=['DELETE'])
def delete_material(material_id):
    current_user_id = DEFAULT_USER_ID
    
    material = Material.query.filter_by(id=material_id, user_id=current_user_id).first()
    
    if not material:
        return jsonify({'error': 'Material not found'}), 404
    
    # 删除相关的分析结果
    AnalysisResult.query.filter_by(material_id=material_id).delete()
    
    # 删除文件
    try:
        if os.path.exists(material.file_path):
            os.remove(material.file_path)
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
    
    # 删除数据库记录
    db.session.delete(material)
    db.session.commit()
    
    return jsonify({'message': 'Material deleted successfully'}), 200

