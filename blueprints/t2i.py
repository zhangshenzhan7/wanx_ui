"""文生图模块蓝图"""
import uuid
from flask import Blueprint, render_template, request, jsonify, session
from services.video_service import VideoService
from services.cache_service import CacheService
from core.handlers.task_handler import TaskHandler
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.validators import validate_pagination

t2i_bp = Blueprint('t2i', __name__)


@t2i_bp.route('/text2image')
def text2image_page():
    """文生图页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('text2image.html')


@t2i_bp.route('/api/create-t2i-task', methods=['POST'])
@require_auth
def create_t2i_task():
    """创建文生图任务"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        prompt = data.get('prompt', '').strip()
        if not prompt:
            return jsonify({'success': False, 'message': '请输入提示词'})
        
        video_service = VideoService(api_key)
        cache_service = CacheService(api_key_hash)
        
        # 提取参数
        params = TaskHandler.extract_task_params(data, 't2i')
        
        # 使用 n 参数指定生成数量，而不是 batch_count 循环
        n = params.get('n', 1)  # 默认生成1张
        
        # z-image-turbo 模型需要串行生成（API每次只支持1张）
        is_z_image = params.get('model') == 'z-image-turbo'
        batch_count = n if is_z_image else 1  # z-image-turbo 需要循环生成
        
        # 生成唯一的 batch_id
        batch_id = uuid.uuid4().hex[:16]
        
        # 创建回调函数用于更新wan2.6-t2i任务的缓存
        # 使用默认参数捕获当前值，避免闭包问题
        def update_t2i_cache(task_id: str, update_data: dict, _cache_service=cache_service, _api_key_hash=api_key_hash):
            """更新文生图任务缓存"""
            try:
                print(f"[DEBUG] 开始更新缓存: {task_id}, status={update_data.get('task_status')}")
                
                # 如果成功，下载图片到本地
                if update_data.get('task_status') == 'SUCCEEDED' and update_data.get('image_urls'):
                    print(f"[DEBUG] 下载图片: {len(update_data['image_urls'])} 张")
                    local_filenames = _cache_service.download_t2i_images(task_id, update_data['image_urls'])
                    if local_filenames:
                        local_image_urls = [f'/api/t2i-image/{_api_key_hash}/{fn}' for fn in local_filenames]
                        update_data['local_image_urls'] = local_image_urls
                        update_data['local_filenames'] = local_filenames
                        print(f"[DEBUG] 图片下载完成: {len(local_filenames)} 个文件")
                
                _cache_service.update_t2i_task(task_id, update_data)
                print(f"[INFO] 已更新wan2.6-t2i任务缓存: {task_id}")
            except Exception as e:
                print(f"[ERROR] 更新wan2.6-t2i任务缓存失败: {task_id}, {e}")
                import traceback
                traceback.print_exc()
        
        created_tasks = []
        
        # z-image-turbo 需要串行生成多张，其他模型一次并行生成
        for i in range(batch_count):
            # 对于wan2.6-t2i和z-image-turbo传递回调函数
            callback = update_t2i_cache if params.get('model') in ['wan2.6-t2i', 'z-image-turbo'] else None
            
            # z-image-turbo 每次生成1张，其他模型生成 n 张
            images_per_task = 1 if is_z_image else n
            
            task_info = video_service.create_t2i_task(
                prompt=prompt,
                model=params.get('model', 'wan2.5-t2i-preview'),
                size=params['size'],
                n=images_per_task,
                negative_prompt=params['negative_prompt'],
                prompt_extend=params['prompt_extend'],
                watermark=params['watermark'],
                callback=callback
            )
            
            if task_info:
                task_info['batch_id'] = batch_id
                task_info['batch_index'] = i + 1
                task_info['batch_total'] = batch_count
                
                cache_service.add_t2i_task(task_info)
                created_tasks.append(task_info)
                
                print(f"[INFO] 创建文生图任务 {i + 1}/{batch_count}: {task_info['task_id']}, 每个任务生成: {images_per_task}张")
                
                # z-image-turbo 串行调用时，在两次调用之间增加延迟防止限流
                if is_z_image and i < batch_count - 1:
                    import time
                    delay = 2  # 每次调用间隔2秒
                    print(f"[INFO] z-image-turbo 串行生成，等待 {delay} 秒后创建下一个任务...")
                    time.sleep(delay)
        
        if created_tasks:
            return jsonify(TaskHandler.build_task_response(created_tasks, batch_id))
        else:
            return jsonify({'success': False, 'message': '创建任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 创建文生图任务失败: {e}")
        return jsonify({'success': False, 'message': f'创建任务失败: {str(e)}'})


@t2i_bp.route('/api/t2i-tasks', methods=['GET'])
@require_auth
def get_t2i_tasks():
    """获取文生图任务列表 - 支持分页"""
    try:
        api_key_hash = get_api_key_hash()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        page, limit = validate_pagination(page, limit)
        
        cache_service = CacheService(api_key_hash)
        tasks, total, has_more = cache_service.get_t2i_tasks_paginated(page, limit)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取文生图任务列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'})


@t2i_bp.route('/api/t2i-task/<task_id>', methods=['GET'])
@require_auth
def get_t2i_task_status(task_id):
    """获取文生图任务状态"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        cache_service = CacheService(api_key_hash)
        cached_task = cache_service.get_t2i_task(task_id)
        
        # wan2.6-t2i和z-image-turbo是同步接口，直接返回结果
        if task_id.startswith('wan26_') or task_id.startswith('zimage_'):
            if cached_task:
                return jsonify({'success': True, 'task': cached_task})
            return jsonify({'success': False, 'message': '任务不存在'})
        
        # 如果任务已经完成，直接返回缓存数据
        if cached_task and cached_task.get('task_status') in ['SUCCEEDED', 'FAILED']:
            return jsonify({'success': True, 'task': cached_task})
        
        # 查询任务状态
        video_service = VideoService(api_key)
        result = video_service.get_task_status(task_id)
        
        if result:
            if result.get('task_status') == 'SUCCEEDED' and result.get('results'):
                image_urls = [img_result.get('url') for img_result in result['results'] if img_result.get('url')]
                result['image_urls'] = image_urls
                
                # 下载图片到本地
                local_filenames = cache_service.download_t2i_images(task_id, image_urls)
                if local_filenames:
                    local_image_urls = [f'/api/t2i-image/{api_key_hash}/{fn}' for fn in local_filenames]
                    result['local_image_urls'] = local_image_urls
                    result['local_filenames'] = local_filenames
            
            cache_service.update_t2i_task(task_id, result)
            return jsonify({'success': True, 'task': result})
        else:
            return jsonify({'success': False, 'message': '查询任务失败'})
    
    except Exception as e:
        print(f"[ERROR] 查询文生图任务失败: {e}")
        return jsonify({'success': False, 'message': f'查询任务失败: {str(e)}'})


@t2i_bp.route('/api/t2i-thumbnails', methods=['GET'])
@require_auth
def get_t2i_thumbnails():
    """获取已完成文生图的缩略图列表 - 支持分页加载（批次分组显示）
    
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
        tasks, total_batches, has_more = cache_service.get_t2i_tasks_paginated(page, limit)
        
        # 按批次分组，每个批次只取一个代表性缩略图
        batch_thumbnails = {}  # batch_id -> thumbnail_info
        standalone_thumbnails = []  # 独立任务的缩略图
        
        for task in tasks:
            if task.get('task_status') != 'SUCCEEDED':
                continue
            
            # 使用第一张图作为缩略图
            poster_url = ''
            if task.get('local_image_urls') and len(task['local_image_urls']) > 0:
                poster_url = task['local_image_urls'][0]
            elif task.get('image_urls') and len(task['image_urls']) > 0:
                poster_url = task['image_urls'][0]
            
            if not poster_url:
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
        print(f"[ERROR] 获取文生图缩略图列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取缩略图列表失败: {str(e)}'})
