"""
统一响应格式化
"""
from flask import jsonify
from datetime import datetime


def success_response(data=None, message='操作成功', **kwargs):
    """
    成功响应
    
    Args:
        data: 响应数据
        message: 响应消息
        **kwargs: 其他字段
        
    Returns:
        JSON响应
    """
    response = {
        'success': True,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    
    if data is not None:
        response['data'] = data
    
    response.update(kwargs)
    
    return jsonify(response)


def error_response(message='操作失败', code='ERROR', status_code=400, **kwargs):
    """
    错误响应
    
    Args:
        message: 错误消息
        code: 错误码
        status_code: HTTP状态码
        **kwargs: 其他字段
        
    Returns:
        JSON响应和状态码
    """
    response = {
        'success': False,
        'error': {
            'code': code,
            'message': message
        },
        'timestamp': datetime.now().isoformat()
    }
    
    response.update(kwargs)
    
    return jsonify(response), status_code
