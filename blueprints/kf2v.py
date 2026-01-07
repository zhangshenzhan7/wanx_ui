"""
首尾帧生视频（KF2V）蓝图模块
包含首尾帧图片上传、任务创建、任务查询等功能
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
kf2v_bp = Blueprint('kf2v', __name__)


@kf2v_bp.route('/kf2v')
def kf2v_page():
    """首尾帧生视频页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('kf2v.html')


@kf2v_bp.route('/api/upload-kf2v-image', methods=['POST'])
@require_auth
def upload_kf2v_image():
    """上传首尾帧图片"""
    try:
        api_key_hash = get_api_key_hash()
        
        if 'image' not in request.files:
            return error_response('没有上传文件')
        
        file = request.files['image']
        frame_type = request.form.get('frame_type', 'first')  # first 或 last
        
        if file.filename == '':
            return error_response('没有选择文件')
        
        # 使用FileService处理文件上传
        file_service = FileService(api_key_hash)
        success, result = file_service.upload_file(file, upload_type='kf2v_image', frame_type=frame_type)
        
        if not success:
            return error_response(result)
        
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'url': result['url'],
            'frame_type': frame_type
        })
    
    except Exception as e:
        return error_response(f'上传失败: {str(e)}')


@kf2v_bp.route('/api/create-kf2v-task', methods=['POST'])
@require_auth
def create_kf2v_task():
    """创建首尾帧生视频任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        # 获取首帧图片路径
        first_frame_filename = data.get('first_frame_filename')
        if not first_frame_filename:
            return error_response('请先上传首帧图片')
        
        first_frame_path = os.path.join(Config.UPLOAD_KF2V_DIR, api_key_hash, first_frame_filename)
        
        # 获取尾帧图片路径
        last_frame_filename = data.get('last_frame_filename')
        if not last_frame_filename:
            return error_response('请先上传尾帧图片')
        
        last_frame_path = os.path.join(Config.UPLOAD_KF2V_DIR, api_key_hash, last_frame_filename)
        
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
            task_info = video_service.create_kf2v_task(
                first_frame_path=first_frame_path,
                last_frame_path=last_frame_path,
                prompt=prompt,
                model=data.get('model', 'wan2.2-kf2v-flash'),
                resolution=data.get('resolution', '720P'),
                negative_prompt=data.get('negative_prompt', ''),
                prompt_extend=data.get('prompt_extend', True)
            )
            
            if task_info:
                # 添加图片文件名和批次信息
                task_info['first_frame_filename'] = first_frame_filename
                task_info['last_frame_filename'] = last_frame_filename
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                # 保存任务信息
                cache_service.add_kf2v_task(task_info)
                
                # 添加图片URL到返回数据
                task_info['first_frame_url'] = f'/api/image/kf2v/{api_key_hash}/{first_frame_filename}'
                task_info['last_frame_url'] = f'/api/image/kf2v/{api_key_hash}/{last_frame_filename}'
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建首尾帧任务 {i + 1}/{batch_count}: {task_info['task_id']}")
        
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
        print(f"[ERROR] 创建首尾帧任务失败: {e}")
        return error_response(f'创建任务失败: {str(e)}')


@kf2v_bp.route('/api/kf2v-tasks', methods=['GET'])
@require_auth
def get_kf2v_tasks():
    """获取首尾帧任务列表 - 支持分页（高性能版本）"""
    try:
        api_key_hash = get_api_key_hash()
        
        # 分页参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)
        
        cache_service = CacheService(api_key_hash)
        
        # 使用高性能分页方法
        tasks, total, has_more = cache_service.get_kf2v_tasks_paginated(page, limit)
        
        # 为每个任务添加图片和视频URL
        for task in tasks:
            if task.get('first_frame_filename'):
                task['first_frame_url'] = f"/api/image/kf2v/{api_key_hash}/{task['first_frame_filename']}"
            if task.get('last_frame_filename'):
                task['last_frame_url'] = f"/api/image/kf2v/{api_key_hash}/{task['last_frame_filename']}"
            if task.get('task_status') == 'SUCCEEDED':
                task['local_video_path'] = f"/api/video/kf2v/{api_key_hash}/{task['task_id']}.mp4"
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取首尾帧任务列表失败: {e}")
        return error_response(f'获取任务列表失败: {str(e)}')


@kf2v_bp.route('/api/kf2v-task/<task_id>', methods=['GET'])
@require_auth
def get_kf2v_task_status(task_id):
    """获取首尾帧任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 查询任务状态
        result = video_service.get_task_status(task_id)
        
        if result:
            # 更新缓存
            cache_service.update_kf2v_task(task_id, result)
            
            # 如果任务完成，下载视频
            if result.get('task_status') == 'SUCCEEDED' and result.get('video_url'):
                video_path = cache_service.download_kf2v_video(task_id, result['video_url'])
                if video_path:
                    result['local_video_path'] = f'/api/video/kf2v/{api_key_hash}/{task_id}.mp4'
            
            return jsonify({'success': True, 'task': result})
        else:
            return error_response('查询任务失败')
    
    except Exception as e:
        print(f"[ERROR] 查询首尾帧任务失败: {e}")
        return error_response(f'查询任务失败: {str(e)}')


@kf2v_bp.route('/api/kf2v-thumbnails', methods=['GET'])
@require_auth
def get_kf2v_thumbnails():
    """获取已完成首尾帧视频的缩略图列表 - 支持分页加载（批次分组显示）
    
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
        tasks, total_batches, has_more = cache_service.get_kf2v_tasks_paginated(page, limit)
        
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
                        'video_path': f"/api/video/kf2v/{api_key_hash}/{task['task_id']}.mp4",
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
                    'video_path': f"/api/video/kf2v/{api_key_hash}/{task['task_id']}.mp4",
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
        print(f"[ERROR] 获取首尾帧视频缩略图列表失败: {e}")
        return error_response(f'获取缩略图列表失败: {str(e)}')
