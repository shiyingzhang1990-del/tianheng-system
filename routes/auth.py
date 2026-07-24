"""登录认证路由 - 简化版，支持直接用户名密码登录"""
from flask import Blueprint, request, jsonify, current_app
from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def ensure_default_user():
    """确保默认管理员用户存在"""
    username = current_app.config.get('DEFAULT_USERNAME', 'admin')
    password = current_app.config.get('DEFAULT_PASSWORD', 'admin123')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, email='admin@tianheng.com')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f" 已创建默认用户: {username} / {password}")
    else:
        # 确保默认用户密码是最新的
        user.set_password(password)
        db.session.commit()


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录 - 返回简单token"""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': '请输入用户名和密码'}), 400
    
    username = data['username'].strip()
    password = data['password']
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 简单token: userid:timestamp:signature
    import hashlib, time
    ts = str(int(time.time()))
    secret = current_app.config.get('SECRET_KEY', 'tianheng-secret-2024')
    raw = f"{user.id}:{ts}:{secret}"
    token = hashlib.sha256(raw.encode()).hexdigest()
    
    return jsonify({
        'success': True,
        'token': f"{user.id}:{ts}:{token}",
        'user': user.to_dict()
    }), 200


@auth_bp.route('/check', methods=['POST'])
def check_login():
    """验证登录状态"""
    data = request.get_json()
    token = data.get('token', '') if data else ''
    
    if not token:
        return jsonify({'valid': False}), 401
    
    parts = token.split(':')
    if len(parts) != 3:
        return jsonify({'valid': False}), 401
    
    user_id, ts, sig = parts
    import hashlib, time
    secret = current_app.config.get('SECRET_KEY', 'tianheng-secret-2024')
    
    # 检查是否过期（30天）
    if int(ts) + 86400 * 30 < time.time():
        return jsonify({'valid': False, 'error': '登录已过期，请重新登录'}), 401
    
    raw = f"{user_id}:{ts}:{secret}"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    
    if sig != expected:
        return jsonify({'valid': False}), 401
    
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({'valid': False}), 404
    
    return jsonify({'valid': True, 'user': user.to_dict()}), 200
