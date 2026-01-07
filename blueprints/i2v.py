"""图生视频模块蓝图"""
import os
from flask import Blueprint, request, jsonify
from config import Config
from services.video_service import VideoService
from services.cache_service import CacheService
from core.services.file_service import FileService
from core.handlers.task_handler import TaskHandler
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.validators import validate_pagination

i2v_bp = Blueprint('i2v', __name__)


@i2v_bp.route('/api/upload-image', methods=['POST'])
@require_auth
def upload_image():
    """上传图片 - 图生视频(I2V)专用"""
    try:
        api_key_hash = get_api_key_hash()
        
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'})

        file = request.files['image']
        
        # 使用FileService处理上传
        file_service = FileService(api_key_hash)
        success, result = file_service.upload_file(file, 'i2v_image')
        
        if success:
            return jsonify({
                'success': True,
                'filename': result['filename'],
                'url': result['url']
            })
        else:
            return jsonify({'success': False, 'message': result})

    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})


@i2v_bp.route('/api/create-task', methods=['POST'])
@require_auth
def create_task():
    """创建图生视频任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        # 获取图片路径
        image_filename = data.get('image_filename')
        if not image_filename:
            return jsonify({'success': False, 'message': '请先上传图片'})
        
        image_path = os.path.join(Config.UPLOAD_I2V_DIR, api_key_hash, image_filename)
        
        # 创建服务
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 提取参数
        params = TaskHandler.extract_task_params(data, 'i2v')
        batch_id, batch_count = TaskHandler.prepare_batch_info(params['batch_count'])
        
        created_tasks = []
        
        # 批量创建任务
        for i in range(batch_count):
            task_info = video_service.create_task(
                image_path=image_path,
                prompt=params['prompt'],
                model=params.get('model', 'wan2.6-i2v'),
                resolution=params['resolution'],
                duration=params['duration'],
                audio_url=params.get('audio_url', ''),
                negative_prompt=params['negative_prompt'],
                prompt_extend=params['prompt_extend'],
                watermark=params['watermark'],
                audio=params['audio']
            )
            
            if task_info:
                # 添加图片文件名和批次信息
                task_info['image_filename'] = image_filename
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                # 保存任务信息
                cache_service.add_task(task_info)
                
                # 添加图片URL
                task_info['image_url'] = f'/api/image/i2v/{api_key_hash}/{image_filename}'
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建图生视频任务 {i + 1}/{batch_count}: {task_info['task_id']}")
        
        if created_tasks:
            return jsonify(TaskHandler.build_task_response(created_tasks, batch_id))
        else:
            return jsonify({'success': False, 'message': '创建任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 创建图生视频任务失败: {e}")
        return jsonify({'success': False, 'message': f'创建任务失败: {str(e)}'})


@i2v_bp.route('/api/tasks', methods=['GET'])
@require_auth
def get_tasks():
    """获取图生视频任务列表 - 支持分页，包含缩略图信息"""
    try:
        api_key_hash = get_api_key_hash()
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        include_thumbnails = request.args.get('include_thumbnails', 'false').lower() == 'true'
        page, limit = validate_pagination(page, limit)
        
        cache_service = CacheService(api_key_hash)
        
        # 使用高性能分页方法
        tasks, total, has_more = cache_service.get_tasks_paginated(page, limit)
        
        # 为每个任务添加图片和视频URL
        for task in tasks:
            if task.get('image_filename'):
                task['image_url'] = f"/api/image/i2v/{api_key_hash}/{task['image_filename']}"
            if task.get('task_status') == 'SUCCEEDED':
                task['local_video_path'] = f"/api/video/i2v/{api_key_hash}/{task['task_id']}.mp4"
                # 如果需要缩略图信息，添加poster_url
                if include_thumbnails:
                    task['poster_url'] = f"/api/video-poster/{api_key_hash}/{task['task_id']}"
        
        response_data = {
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        }
        
        # 如果请求包含缩略图，生成缩略图列表
        if include_thumbnails:
            thumbnails = []
            batch_thumbnails = {}
            
            for task in tasks:
                if task.get('task_status') != 'SUCCEEDED':
                    continue
                
                batch_id = task.get('batch_id')
                batch_total = task.get('batch_total', 1)
                
                if batch_id:
                    if batch_id not in batch_thumbnails:
                        batch_thumbnails[batch_id] = {
                            'task_id': task['task_id'],
                            'batch_id': batch_id,
                            'batch_total': batch_total,
                            'batch_completed': 1,
                            'poster_url': task.get('poster_url'),
                            'type': 'video'
                        }
                    else:
                        batch_thumbnails[batch_id]['batch_completed'] += 1
                else:
                    thumbnails.append({
                        'task_id': task['task_id'],
                        'batch_id': None,
                        'poster_url': task.get('poster_url'),
                        'type': 'video'
                    })
            
            # 按顺序合并缩略图
            for task in tasks:
                batch_id = task.get('batch_id')
                if batch_id and batch_id in batch_thumbnails:
                    thumbnails.append(batch_thumbnails[batch_id])
                    del batch_thumbnails[batch_id]  # 避免重复
            
            response_data['thumbnails'] = thumbnails
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"[ERROR] 获取任务列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'})

@i2v_bp.route('/api/task/<task_id>', methods=['GET'])
@require_auth
def get_task_status(task_id):
    """获取图生视频任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 查询任务状态
        result = video_service.get_task_status(task_id)
        
        if result:
            # 更新缓存
            cache_service.update_task(task_id, result)
            
            # 如果任务完成，下载视频
            if result.get('task_status') == 'SUCCEEDED' and result.get('video_url'):
                video_path = cache_service.download_video(task_id, result['video_url'])
                if video_path:
                    result['local_video_path'] = f'/api/video/i2v/{api_key_hash}/{task_id}.mp4'
            
            return jsonify({'success': True, 'task': result})
        else:
            return jsonify({'success': False, 'message': '查询任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 查询任务失败: {e}")
        return jsonify({'success': False, 'message': f'查询任务失败: {str(e)}'})


@i2v_bp.route('/api/video-thumbnails', methods=['GET'])
@require_auth
def get_video_thumbnails():
    """获取已完成视频的缩略图列表 - 支持分页加载（批次分组显示）
    
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
        tasks, total_batches, has_more = cache_service.get_tasks_paginated(page, limit)
        
        # 按批次分组，每个批次只取一个代表性缩略图
        batch_thumbnails = {}  # batch_id -> thumbnail_info
        standalone_thumbnails = []  # 独立任务的缩略图
        
        for task in tasks:
            if task.get('task_status') != 'SUCCEEDED':
                continue
            
            batch_id = task.get('batch_id')
            batch_total = task.get('batch_total', 1)
            
            if batch_id:
                # 批次任务：只保留第一个完成的任务作为代表
                if batch_id not in batch_thumbnails:
                    batch_thumbnails[batch_id] = {
                        'task_id': task['task_id'],
                        'batch_id': batch_id,
                        'batch_total': batch_total,
                        'batch_completed': 1,
                        'poster_url': f"/api/video-poster/{api_key_hash}/{task['task_id']}",
                        'video_path': f"/api/video/i2v/{api_key_hash}/{task['task_id']}.mp4",
                        'type': 'video'
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
                    'poster_url': f"/api/video-poster/{api_key_hash}/{task['task_id']}",
                    'video_path': f"/api/video/i2v/{api_key_hash}/{task['task_id']}.mp4",
                    'type': 'video'
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
            'total_tasks': total_batches,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取视频缩略图列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取缩略图列表失败: {str(e)}'})


@i2v_bp.route('/api/task-locate/<task_id>', methods=['GET'])
@require_auth
def locate_task(task_id):
    """定位任务所在页码 - 用于缩略图导航快速定位
    
    Returns:
        {
            success: bool,
            page: int,  # 任务所在页码
            index_in_page: int,  # 页内索引
            batch_id: str  # 批次ID（如果有）
        }
    """
    try:
        api_key_hash = get_api_key_hash()
        cache_service = CacheService(api_key_hash)
        
        # 尝试从索引中定位
        location = cache_service.locate_task(task_id, 'i2v')
        
        if location:
            return jsonify({
                'success': True,
                'page': location['page'],
                'index_in_page': location['index_in_page'],
                'batch_id': location.get('batch_id')
            })
        else:
            return jsonify({
                'success': False,
                'message': '未找到任务位置信息'
            })
    
    except Exception as e:
        print(f"[ERROR] 定位任务失败: {e}")
        return jsonify({'success': False, 'message': f'定位任务失败: {str(e)}'})


@i2v_bp.route('/api/task-index', methods=['GET'])
@require_auth
def get_task_index():
    """获取任务索引 - 返回所有任务的页码信息
    
    这个接口返回轻量级索引数据，用于前端缓存和快速定位
    """
    try:
        api_key_hash = get_api_key_hash()
        cache_service = CacheService(api_key_hash)
        
        # 加载或重建索引
        index_data = cache_service.load_task_index('i2v')
        
        if not index_data['task_index']:
            # 索引不存在，重建
            index_data = cache_service.rebuild_task_index('i2v')
        
        return jsonify({
            'success': True,
            'total_count': index_data['total_count'],
            'last_updated': index_data['last_updated'],
            'task_index': index_data['task_index']
        })
    
    except Exception as e:
        print(f"[ERROR] 获取任务索引失败: {e}")
        return jsonify({'success': False, 'message': f'获取任务索引失败: {str(e)}'})