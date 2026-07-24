"""授权验证路由 - 简化版，始终返回有效"""
from flask import Blueprint, jsonify
from datetime import datetime

license_bp = Blueprint('license', __name__, url_prefix='/api/license')


@license_bp.route('/machine-code', methods=['GET'])
def get_machine_code_route():
    """获取机器码（简化版，返回固定值）"""
    return jsonify({
        'code': 200,
        'message': '获取成功',
        'data': {
            'machine_code': 'TIANHENG-FREE-EDITION'
        }
    }), 200


@license_bp.route('/verify', methods=['POST'])
def verify_license():
    """验证授权 - 始终返回有效"""
    return jsonify({
        'code': 200,
        'msg': '授权有效',
        'valid': True,
        'data': {
            'valid': True,
            'machine_code': 'TIANHENG-FREE-EDITION',
            'expire_time': '2099-12-31 23:59:59',
            'license_key': 'FREE-EDITION-NO-LIMIT'
        }
    }), 200


@license_bp.route('/status', methods=['GET'])
def get_license_status():
    """获取授权状态 - 始终有效"""
    return jsonify({
        'code': 200,
        'message': '授权有效（免费版）',
        'data': {
            'valid': True,
            'machine_code': 'TIANHENG-FREE-EDITION',
            'expire_time': '2099-12-31 23:59:59'
        }
    }), 200
