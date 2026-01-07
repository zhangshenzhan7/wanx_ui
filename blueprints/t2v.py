"""文生视频模块蓝图"""
from flask import Blueprint, render_template, request, jsonify, session
from services.video_service import VideoService
from services.cache_service import CacheService
from core.handlers.task_handler import TaskHandler
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.validators import validate_pagination

t2v_bp = Blueprint('t2v', __name__)


@t2v_bp.route('/text2video')
def text2video_page():
    """文生视频页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('text2video.html')


@t2v_bp.route('/api/create-t2v-task', methods=['POST'])
@require_auth
def create_t2v_task():
    """创建文生视频任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        # 验证提示词
        prompt = data.get('prompt', '').strip()
        if not prompt:
            return jsonify({'success': False, 'message': '请输入提示词'})
        
        # 创建服务
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 提取参数
        params = TaskHandler.extract_task_params(data, 't2v')
        batch_id, batch_count = TaskHandler.prepare_batch_info(params['batch_count'])
        
        created_tasks = []
        
        # 批量创建任务
        for i in range(batch_count):
            task_info = video_service.create_t2v_task(
                prompt=prompt,
                model=params.get('model', 'wan2.6-t2v'),
                resolution=params['resolution'],
                duration=params['duration'],
                audio=params['audio'],
                audio_url=params.get('audio_url', ''),
                negative_prompt=params['negative_prompt'],
                shot_type=params['shot_type']
            )
            
            if task_info:
                # 添加批次信息
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                # 保存任务信息
                cache_service.add_t2v_task(task_info)
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建文生视频任务 {i + 1}/{batch_count}: {task_info['task_id']}")
        
        if created_tasks:
            return jsonify(TaskHandler.build_task_response(created_tasks, batch_id))
        else:
            return jsonify({'success': False, 'message': '创建任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 创建文生视频任务失败: {e}")
        return jsonify({'success': False, 'message': f'创建任务失败: {str(e)}'})


@t2v_bp.route('/api/t2v-tasks', methods=['GET'])
@require_auth
def get_t2v_tasks():
    """获取文生视频任务列表 - 支持分页"""
    try:
        api_key_hash = get_api_key_hash()
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        page, limit = validate_pagination(page, limit)
        
        cache_service = CacheService(api_key_hash)
        
        # 使用高性能分页方法
        tasks, total, has_more = cache_service.get_t2v_tasks_paginated(page, limit)
        
        # 为每个任务添加视频URL
        for task in tasks:
            if task.get('task_status') == 'SUCCEEDED':
                task['local_video_path'] = f"/api/video/t2v/{api_key_hash}/{task['task_id']}.mp4"
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取文生视频任务列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'})


@t2v_bp.route('/api/t2v-task/<task_id>', methods=['GET'])
@require_auth
def get_t2v_task_status(task_id):
    """获取文生视频任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 查询任务状态
        result = video_service.get_task_status(task_id)
        
        if result:
            # 更新缓存
            cache_service.update_t2v_task(task_id, result)
            
            # 如果任务完成，下载视频
            if result.get('task_status') == 'SUCCEEDED' and result.get('video_url'):
                video_path = cache_service.download_t2v_video(task_id, result['video_url'])
                if video_path:
                    result['local_video_path'] = f'/api/video/t2v/{api_key_hash}/{task_id}.mp4'
            
            return jsonify({'success': True, 'task': result})
        else:
            return jsonify({'success': False, 'message': '查询任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 查询文生视频任务失败: {e}")
        return jsonify({'success': False, 'message': f'查询任务失败: {str(e)}'})


@t2v_bp.route('/api/t2v-thumbnails', methods=['GET'])
@require_auth
def get_t2v_thumbnails():
    """获取已完成文生视频的缩略图列表 - 支持分页加载
    
    返回轻量级数据，只包含 task_id 和 poster_url，支持无限滚动加载
    """
    try:
        api_key_hash = get_api_key_hash()
        cache_service = CacheService(api_key_hash)
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # 最大100个
        
        # 获取任务列表
        tasks, total_tasks, _ = cache_service.get_t2v_tasks_paginated(page, limit)
        
        # 提取已完成视频的缩略图信息
        thumbnails = []
        for task in tasks:
            if task.get('task_status') == 'SUCCEEDED':
                batch_id = task.get('batch_id')
                thumbnails.append({
                    'task_id': task['task_id'],
                    'batch_id': batch_id,
                    'batch_index': task.get('batch_index', 1),
                    'poster_url': f"/api/video-poster/{api_key_hash}/{task['task_id']}",
                    'video_path': f"/api/video/t2v/{api_key_hash}/{task['task_id']}.mp4",
                    'type': 'video'
                })
        
        # 计算是否还有更多
        has_more = (page * limit) < total_tasks
        
        return jsonify({
            'success': True,
            'thumbnails': thumbnails,
            'page': page,
            'limit': limit,
            'total_tasks': total_tasks,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取文生视频缩略图列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取缩略图列表失败: {str(e)}'})
