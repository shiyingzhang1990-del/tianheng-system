"""
文件处理工具函数
"""
import time
from werkzeug.utils import secure_filename

def safe_filename(original_filename, prefix="upload"):
    """
    安全地处理文件名，统一使用时间戳格式
    
    参数:
    original_filename (str): 原始文件名
    prefix (str): 文件名前缀，用于生成安全文件名
    
    返回:
    str: 安全的文件名，格式为 prefix_timestamp.extension
    """
    if not original_filename:
        return f"{prefix}_{int(time.time())}"
    
    # 从原始文件名提取扩展名
    original_extension = ''
    if '.' in original_filename:
        try:
            original_extension = '.' + original_filename.rsplit('.', 1)[1].lower()
        except (IndexError, AttributeError):
            original_extension = ''
    
    # 统一生成带时间戳的文件名
    timestamp = int(time.time())
    filename = f"{prefix}_{timestamp}{original_extension}"
    
    return filename

def get_file_extension(original_filename):
    """
    从原始文件名提取文件扩展名
    
    参数:
    original_filename (str): 原始文件名
    
    返回:
    str: 文件扩展名（不包含点号）
    """
    if not original_filename or '.' not in original_filename:
        return 'txt'
    
    try:
        return original_filename.rsplit('.', 1)[1].lower()
    except (IndexError, AttributeError):
        return 'txt'
