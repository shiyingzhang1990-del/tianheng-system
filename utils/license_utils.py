"""
授权相关工具函数
"""
import uuid
import platform
import hashlib
import os


def get_machine_code():
    """
    获取机器码
    基于多个硬件特征生成唯一标识
    """
    try:
        # 获取系统信息
        system = platform.system()
        node = platform.node()
        machine = platform.machine()
        processor = platform.processor()
        
        # 获取MAC地址
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        
        # 组合所有信息
        machine_info = f"{system}-{node}-{machine}-{processor}-{mac}"
        
        # 生成SHA256哈希
        machine_hash = hashlib.sha256(machine_info.encode()).hexdigest()
        
        # 返回前16位作为机器码（更简洁）
        return machine_hash[:16].upper()
    except Exception as e:
        print(f"获取机器码失败: {e}")
        # 如果失败，使用备用方案
        fallback = hashlib.md5(str(uuid.getnode()).encode()).hexdigest()
        return fallback[:16].upper()


def verify_license_format(license_key):
    """
    验证授权码格式
    格式: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX (32字符，8组)
    """
    if not license_key:
        return False
    
    # 移除可能的分隔符
    cleaned = license_key.replace('-', '').replace(' ', '')
    
    # 检查长度和字符
    if len(cleaned) != 32:
        return False
    
    # 检查是否都是十六进制字符
    try:
        int(cleaned, 16)
        return True
    except ValueError:
        return False


def format_license_key(license_key):
    """
    格式化授权码为易读格式
    """
    cleaned = license_key.replace('-', '').replace(' ', '')
    if len(cleaned) != 32:
        return license_key
    
    # 分成8组，每组4个字符
    groups = [cleaned[i:i+4] for i in range(0, 32, 4)]
    return '-'.join(groups)

