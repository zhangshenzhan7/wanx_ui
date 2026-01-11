"""
参考生视频（R2V）蓝图模块
包含参考视频上传、任务创建、任务查询等功能
"""

from flask import Blueprint, render_template, request, jsonify, session
import os
import uuid

from config import Config
from services.video_service import VideoService
from services.cache_service import CacheService
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.response_helper import success_response, error_response
from core.utils.validators import validate_batch_count
from core.services.file_service import FileService


# 创建蓝图
r2v_bp = Blueprint('r2v', __name__)


@r2v_bp.route('/reference2video')
def reference2video_page():
    """参考生视频页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('reference2video.html')


@r2v_bp.route('/api/upload-r2v-video', methods=['POST'])
@require_auth
def upload_r2v_video():
    """上传参考视频 - R2V专用"""
    try:
        api_key_hash = get_api_key_hash()
        
        if 'video' not in request.files:
            return error_response('没有上传文件')
        
        file = request.files['video']
        if file.filename == '':
            return error_response('没有选择文件')
        
        # 使用FileService处理文件上传
        file_service = FileService(api_key_hash)
        success, result = file_service.upload_file(file, upload_type='r2v_video')
        
        if not success:
            return error_response(result)
        
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'url': result['url']
        })
    
    except Exception as e:
        return error_response(f'上传失败: {str(e)}')


@r2v_bp.route('/api/create-r2v-task', methods=['POST'])
@require_auth
def create_r2v_task():
    """创建参考生视频任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        # 获取参考视频文件名
        reference_video_filenames = data.get('reference_video_filenames', [])
        if not reference_video_filenames or len(reference_video_filenames) == 0:
            return error_response('请先上传参考视频')
        
        if len(reference_video_filenames) > 3:
            return error_response('最多只能上传3个参考视频')
        
        # 构建视频路径列表
        reference_video_paths = []
        for filename in reference_video_filenames:
            video_path = os.path.join(Config.UPLOAD_R2V_DIR, api_key_hash, filename)
            if not os.path.exists(video_path):
                return error_response(f'视频文件不存在: {filename}')
            reference_video_paths.append(video_path)
        
        # 验证提示词
        prompt = data.get('prompt', '').strip()
        if not prompt:
            return error_response('请输入提示词')
        
        # 创建服务
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 批量任务处理
        batch_count = validate_batch_count(data.get('batch_count', 1))
        batch_id = str(uuid.uuid4()) if batch_count > 1 else None
        
        created_tasks = []
        
        # 批量创建任务
        for i in range(batch_count):
            task_info = video_service.create_r2v_task(
                reference_video_paths=reference_video_paths,
                prompt=prompt,
                model=data.get('model', 'wan2.6-r2v'),
                size=data.get('size', '1280*720'),
                duration=int(data.get('duration', 5)),
                shot_type=data.get('shot_type', 'single'),
                negative_prompt=data.get('negative_prompt', ''),
                seed=data.get('seed'),
                watermark=data.get('watermark', False),
                audio=data.get('audio', True)  # 支持音频参数
            )
            
            if task_info:
                # 添加视频文件名和批次信息
                task_info['reference_video_filenames'] = reference_video_filenames
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                # 保存任务信息
                cache_service.add_r2v_task(task_info)
                
                # 添加视频URL到返回数据
                task_info['reference_video_urls'] = [
                    f'/api/video/r2v/{api_key_hash}/{fn}' for fn in reference_video_filenames
                ]
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建参考生视频任务 {i + 1}/{batch_count}: {task_info['task_id']}")
        
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
        print(f"[ERROR] 创建参考生视频任务失败: {e}")
        return error_response(f'创建任务失败: {str(e)}')


@r2v_bp.route('/api/r2v-tasks', methods=['GET'])
@require_auth
def get_r2v_tasks():
    """获取参考生视频任务列表 - 支持分页（高性能版本）"""
    try:
        api_key_hash = get_api_key_hash()
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)
        
        cache_service = CacheService(api_key_hash)
        
        # 使用高性能分页方法
        tasks, total, has_more = cache_service.get_r2v_tasks_paginated(page, limit)
        
        # 为每个任务添加视频URL
        for task in tasks:
            if task.get('reference_video_filenames'):
                task['reference_video_urls'] = [
                    f"/api/video/r2v/{api_key_hash}/{fn}" for fn in task['reference_video_filenames']
                ]
            if task.get('task_status') == 'SUCCEEDED':
                task['local_video_path'] = f"/api/video/r2v/{api_key_hash}/{task['task_id']}.mp4"
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取参考生视频任务列表失败: {e}")
        return error_response(f'获取任务列表失败: {str(e)}')


@r2v_bp.route('/api/r2v-task/<task_id>', methods=['GET'])
@require_auth
def get_r2v_task_status(task_id):
    """获取参考生视频任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 查询任务状态
        result = video_service.get_task_status(task_id)
        
        if result:
            # 更新缓存
            cache_service.update_r2v_task(task_id, result)
            
            # 如果任务完成，下载视频
            if result.get('task_status') == 'SUCCEEDED' and result.get('video_url'):
                video_path = cache_service.download_r2v_video(task_id, result['video_url'])
                if video_path:
                    result['local_video_path'] = f'/api/video/r2v/{api_key_hash}/{task_id}.mp4'
            
            return jsonify({'success': True, 'task': result})
        else:
            return error_response('查询任务失败')
    
    except Exception as e:
        print(f"[ERROR] 查询参考生视频任务失败: {e}")
        return error_response(f'查询任务失败: {str(e)}')


@r2v_bp.route('/api/r2v-thumbnails', methods=['GET'])
@require_auth
def get_r2v_thumbnails():
    """获取已完成参考视频的缩略图列表 - 支持分页加载（批次分组显示）
    
    返回轻量级数据，按批次分组，每个批次只显示一个代表性缩略图
    """
    try:
        api_key_hash = get_api_key_hash()
        cache_service = CacheService(api_key_hash)
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # 最大100个
        
        # 获取任务列表
        tasks, total_batches, has_more = cache_service.get_r2v_tasks_paginated(page, limit)
        
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
                        'video_path': f"/api/video/r2v/{api_key_hash}/{task['task_id']}.mp4",
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
                    'video_path': f"/api/video/r2v/{api_key_hash}/{task['task_id']}.mp4",
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
        print(f"[ERROR] 获取参考视频缩略图列表失败: {e}")
        return error_response(f'获取缩略图列表失败: {str(e)}')
