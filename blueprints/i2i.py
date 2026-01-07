"""
图生图（I2I）蓝图模块
包含图片上传、任务创建、任务查询等功能
"""

from flask import Blueprint, render_template, request, jsonify, session
from functools import wraps
import os
import time
import uuid

from config import Config
from services.video_service import VideoService
from services.cache_service import CacheService
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.response_helper import success_response, error_response
from core.utils.validators import validate_batch_count
from core.services.file_service import FileService
from core.handlers.task_handler import TaskHandler


# 创建蓝图
i2i_bp = Blueprint('i2i', __name__)


@i2i_bp.route('/image2image')
def image2image_page():
    """图生图页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('image2image.html')


@i2i_bp.route('/api/upload-i2i-image', methods=['POST'])
@require_auth
def upload_i2i_image():
    """上传图片 - 图生图(I2I)专用"""
    try:
        api_key_hash = get_api_key_hash()
        
        if 'image' not in request.files:
            return error_response('没有上传文件')
        
        file = request.files['image']
        if file.filename == '':
            return error_response('没有选择文件')
        
        # 使用FileService处理文件上传
        file_service = FileService(api_key_hash)
        success, result = file_service.upload_file(file, upload_type='i2i_image')
        
        if not success:
            return error_response(result)
        
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'url': result['url']
        })
    
    except Exception as e:
        return error_response(f'上传失败: {str(e)}')


@i2i_bp.route('/api/create-i2i-task', methods=['POST'])
@require_auth
def create_i2i_task():
    """创建图生图任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        # 验证参考图片
        image_filenames = data.get('image_filenames', [])
        if not image_filenames or len(image_filenames) == 0:
            return error_response('请先上传参考图片')
        
        if len(image_filenames) > 3:
            return error_response('最多只能上传3张参考图片')
        
        # 验证图片文件是否存在
        image_paths = []
        for filename in image_filenames:
            image_path = os.path.join(Config.UPLOAD_I2I_DIR, api_key_hash, filename)
            if not os.path.exists(image_path):
                return error_response(f'图片文件不存在: {filename}')
            image_paths.append(image_path)
        
        # 验证提示词
        prompt = data.get('prompt', '').strip()
        if not prompt:
            return error_response('请输入提示词')
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 批量任务处理
        batch_count = validate_batch_count(data.get('batch_count', 1))
        batch_id = str(uuid.uuid4()) if batch_count > 1 else None
        
        model = data.get('model', 'wan2.5-i2i-preview')
        
        # 为qwen-image-edit-plus创建后台任务回调函数
        def qwen_task_callback(task_id: str, update_data: dict):
            """qwen-image-edit-plus后台任务完成回调"""
            try:
                callback_cache_service = CacheService(api_key_hash)
                
                # 如果任务成功，下载图片到本地
                if update_data.get('task_status') == 'SUCCEEDED' and update_data.get('results'):
                    image_urls = update_data['results']
                    local_filenames = callback_cache_service.download_i2i_images(task_id, image_urls)
                    if local_filenames:
                        local_image_urls = [f'/api/i2i-image/{api_key_hash}/{fn}' for fn in local_filenames]
                        update_data['local_image_urls'] = local_image_urls
                        update_data['local_filenames'] = local_filenames
                        print(f"[INFO] qwen-image-edit-plus 图片已保存到本地: {local_filenames}")
                
                # 更新缓存
                callback_cache_service.update_i2i_task(task_id, update_data)
                print(f"[INFO] qwen-image-edit-plus 任务缓存已更新: {task_id}, status={update_data.get('task_status')}")
            except Exception as e:
                print(f"[ERROR] qwen-image-edit-plus 回调处理失败: {task_id}, {e}")
        
        created_tasks = []
        
        for i in range(batch_count):
            # 准备wan2.6-image图文混排模式参数
            callback_param = None
            if model == 'wan2.6-image':
                # 通过特殊字典传递enable_interleave和max_images参数
                callback_param = {
                    'enable_interleave': data.get('enable_interleave', False),
                    'max_images': data.get('max_images', 5)
                }
            elif model == 'qwen-image-edit-plus':
                callback_param = qwen_task_callback
            
            task_info = video_service.create_i2i_task(
                image_paths=image_paths,
                prompt=prompt,
                model=model,
                size=data.get('size'),  # 可选参数，qwen-image-edit-plus不传递
                n=1,
                prompt_extend=data.get('prompt_extend', True),
                negative_prompt=data.get('negative_prompt', ''),
                callback=callback_param
            )
            
            if task_info:
                task_info['image_filenames'] = image_filenames
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                # 添加参考图片URL到任务信息中
                reference_image_urls = []
                for filename in image_filenames:
                    reference_image_urls.append(f'/api/image/i2i/{api_key_hash}/{filename}')
                task_info['reference_image_urls'] = reference_image_urls
                
                cache_service.add_i2i_task(task_info)
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建图生图任务 {i + 1}/{batch_count}: {task_info['task_id']}")
        
        if created_tasks:
            message = f'成功创建{batch_count}个任务' if batch_count > 1 else '任务创建成功'
            return jsonify({
                'success': True,
                'tasks': created_tasks,
                'batch_id': batch_id,
                'message': message
            })
        else:
            return error_response('创建任务失败')
    
    except Exception as e:
        print(f"[ERROR] 创建图生图任务失败: {e}")
        return error_response(f'创建任务失败: {str(e)}')


@i2i_bp.route('/api/i2i-tasks', methods=['GET'])
@require_auth
def get_i2i_tasks():
    """获取图生图任务列表 - 支持分页（高性能版本）"""
    try:
        api_key_hash = get_api_key_hash()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)
        
        cache_service = CacheService(api_key_hash)
        
        # 使用高性能分页方法
        tasks, total, has_more = cache_service.get_i2i_tasks_paginated(page, limit)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取图生图任务列表失败: {e}")
        return error_response(f'获取任务列表失败: {str(e)}')


@i2i_bp.route('/api/i2i-task/<task_id>', methods=['GET'])
@require_auth
def get_i2i_task_status(task_id):
    """获取图生图任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        cache_service = CacheService(api_key_hash)
        
        # 先检查缓存中的任务状态
        cached_task = cache_service.get_i2i_task(task_id)
        
        # 如果任务已经完成（SUCCEEDED或FAILED），直接返回缓存数据
        if cached_task and cached_task.get('task_status') in ['SUCCEEDED', 'FAILED']:
            return jsonify({'success': True, 'task': cached_task})
        
        # qwen-image-edit-plus 任务使用自定义task_id，不需要查询DashScope API
        # 后台线程完成后会通过回调更新缓存
        if task_id.startswith('qwen_'):
            if cached_task:
                return jsonify({'success': True, 'task': cached_task})
            return error_response('任务不存在')
        
        # 对于未完成的任务，调用DashScope API查询状态
        video_service = VideoService(api_key)
        result = video_service.get_task_status(task_id)
        
        if result:
            if result.get('task_status') == 'SUCCEEDED' and result.get('results'):
                image_urls = []
                for img_result in result['results']:
                    if img_result.get('url'):
                        image_urls.append(img_result['url'])
                result['image_urls'] = image_urls
                
                # 下载图片到本地存储
                local_filenames = cache_service.download_i2i_images(task_id, image_urls)
                if local_filenames:
                    # 生成本地图片URL
                    local_image_urls = [f'/api/i2i-image/{api_key_hash}/{fn}' for fn in local_filenames]
                    result['local_image_urls'] = local_image_urls
                    result['local_filenames'] = local_filenames
                    print(f"[INFO] 图生图任务图片已保存到本地: {local_filenames}")
            
            cache_service.update_i2i_task(task_id, result)
            return jsonify({'success': True, 'task': result})
        else:
            # 如果DashScope API查询失败，返回缓存数据（如果有）
            if cached_task:
                return jsonify({'success': True, 'task': cached_task})
            return error_response('查询任务失败')
    
    except Exception as e:
        print(f"[ERROR] 查询图生图任务失败: {e}")
        return error_response(f'查询任务失败: {str(e)}')


@i2i_bp.route('/api/i2i-thumbnails', methods=['GET'])
@require_auth
def get_i2i_thumbnails():
    """获取已完成图生图的缩略图列表 - 支持分页加载（批次分组显示）
    
    返回轻量级数据，按批次分组，每个批次只显示一个代表性缩略图
    """
    try:
        api_key_hash = get_api_key_hash()
        cache_service = CacheService(api_key_hash)
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # 最大100个
        
        # 获取任务列表（已经按批次分组）
        tasks, total_batches, has_more = cache_service.get_i2i_tasks_paginated(page, limit)
        
        # 按批次分组，每个批次只取一个代表性缩略图
        batch_thumbnails = {}  # batch_id -> thumbnail_info
        standalone_thumbnails = []  # 独立任务的缩略图
        
        for task in tasks:
            if task.get('task_status') != 'SUCCEEDED':
                continue
                
            # 获取缩略图URL
            poster_url = ''
            if task.get('local_image_urls') and len(task['local_image_urls']) > 0:
                poster_url = task['local_image_urls'][0]
            elif task.get('image_urls') and len(task['image_urls']) > 0:
                poster_url = task['image_urls'][0]
            
            if not poster_url:
                continue
            
            batch_id = task.get('batch_id')
            batch_index = task.get('batch_index', 1)
            batch_total = task.get('batch_total', 1)
            
            if batch_id:
                # 批次任务：只保留第一个完成的任务作为代表
                if batch_id not in batch_thumbnails:
                    batch_thumbnails[batch_id] = {
                        'task_id': task['task_id'],
                        'batch_id': batch_id,
                        'batch_total': batch_total,
                        'batch_completed': 1,
                        'poster_url': poster_url,
                        'type': 'image'
                    }
                else:
                    # 增加已完成计数
                    batch_thumbnails[batch_id]['batch_completed'] += 1
            else:
                # 独立任务
                standalone_thumbnails.append({
                    'task_id': task['task_id'],
                    'batch_id': None,
                    'batch_total': 1,
                    'batch_completed': 1,
                    'poster_url': poster_url,
                    'type': 'image'
                })
        
        # 合并缩略图列表，保持原有顺序
        thumbnails = []
        seen_batch_ids = set()
        
        for task in tasks:
            batch_id = task.get('batch_id')
            task_id = task.get('task_id')
            
            if batch_id:
                if batch_id not in seen_batch_ids and batch_id in batch_thumbnails:
                    thumbnails.append(batch_thumbnails[batch_id])
                    seen_batch_ids.add(batch_id)
            else:
                # 查找对应的独立任务缩略图
                for st in standalone_thumbnails:
                    if st['task_id'] == task_id:
                        thumbnails.append(st)
                        break
        
        return jsonify({
            'success': True,
            'thumbnails': thumbnails,
            'page': page,
            'limit': limit,
            'total_tasks': len(thumbnails),  # 返回实际缩略图数量
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取图生图缩略图列表失败: {e}")
        return error_response(f'获取缩略图列表失败: {str(e)}')
