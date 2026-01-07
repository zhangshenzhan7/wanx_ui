"""响应辅助工具"""
from flask import jsonify, Response


def success_response(data=None, message='操作成功'):
    """构建成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        
    Returns:
        JSON响应对象
    """
    response = {'success': True, 'message': message}
    if data is not None:
        response.update(data if isinstance(data, dict) else {'data': data})
    return jsonify(response)


def error_response(message='操作失败', code=400):
    """构建错误响应
    
    Args:
        message: 错误消息
        code: HTTP状态码
        
    Returns:
        JSON响应对象和状态码
    """
    return jsonify({'success': False, 'message': message}), code


def paginated_response(items, page, limit, total, has_more=None):
    """构建分页响应
    
    Args:
        items: 数据列表
        page: 当前页码
        limit: 每页数量
        total: 总数量
        has_more: 是否有更多数据（可选）
        
    Returns:
        JSON响应对象
    """
    response = {
        'success': True,
        'data': items,
        'page': page,
        'limit': limit,
        'total': total
    }
    
    if has_more is not None:
        response['has_more'] = has_more
    
    return jsonify(response)


def stream_response(generator, mimetype='text/event-stream'):
    """构建流式响应（SSE）
    
    Args:
        generator: 生成器函数
        mimetype: MIME类型
        
    Returns:
        流式响应对象
    """
    return Response(
        generator,
        mimetype=mimetype,
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )
