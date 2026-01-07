"""参数验证工具"""


def validate_required(data, fields):
    """验证必需字段
    
    Args:
        data: 数据字典
        fields: 必需字段列表或字典（字段名: 显示名称）
        
    Returns:
        (is_valid, error_message)
    """
    if isinstance(fields, dict):
        for field, display_name in fields.items():
            if not data.get(field):
                return False, f'{display_name}不能为空'
    else:
        for field in fields:
            if not data.get(field):
                return False, f'{field}不能为空'
    
    return True, None


def validate_file_extension(filename, allowed_exts):
    """验证文件扩展名
    
    Args:
        filename: 文件名
        allowed_exts: 允许的扩展名集合（如 {'png', 'jpg', 'jpeg'}）
        
    Returns:
        (is_valid, error_message)
    """
    if not filename or '.' not in filename:
        return False, '无效的文件名'
    
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_exts:
        return False, f'不支持的文件格式，仅支持: {", ".join(allowed_exts)}'
    
    return True, None


def validate_batch_count(count, max_count=4):
    """验证批次数量
    
    Args:
        count: 批次数量
        max_count: 最大批次数量
        
    Returns:
        validated_count (限制在1到max_count之间)
    """
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 1
    
    return max(1, min(max_count, count))


def validate_pagination(page, limit, max_limit=50):
    """验证分页参数
    
    Args:
        page: 页码
        limit: 每页数量
        max_limit: 最大每页数量
        
    Returns:
        (validated_page, validated_limit)
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    
    try:
        limit = int(limit)
        limit = max(1, min(max_limit, limit))
    except (TypeError, ValueError):
        limit = 10
    
    return page, limit
