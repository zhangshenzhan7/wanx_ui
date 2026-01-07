"""Session 辅助工具"""
from flask import session
import hashlib
from functools import wraps


def get_api_key():
    """从session获取API Key"""
    return session.get('api_key')


def get_api_key_hash():
    """从session获取API Key哈希"""
    return session.get('api_key_hash')


def generate_api_key_hash(api_key: str) -> str:
    """生成API Key哈希
    
    Args:
        api_key: API Key字符串
        
    Returns:
        API Key的SHA256哈希值（前16位）
    """
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def require_auth(f):
    """装饰器：要求认证
    
    用于保护需要登录的路由，如果用户未登录则返回错误
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import jsonify
        
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        if not api_key or not api_key_hash:
            return jsonify({'success': False, 'message': '请先输入API Key'}), 401
            
        return f(*args, **kwargs)
    
    return decorated_function
