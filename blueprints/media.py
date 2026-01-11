"""媒体文件服务模块蓝图"""
import os
import json
from flask import Blueprint, request, jsonify, send_file, make_response
from config import Config
from core.handlers.media_handler import MediaHandler
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from services.audio_service import AudioService
from services.cache_service import CacheService
from services.video_service import VideoService

media_bp = Blueprint('media', __name__)


# ========== 图片服务 ==========

@media_bp.route('/api/image/<task_type>/<api_key_hash>/<filename>')
def get_image(task_type, api_key_hash, filename):
    """获取上传的图片
    
    task_type: i2v(图生视频), kf2v(首尾帧), i2i(图生图)
    """
    try:
        # 根据任务类型选择目录
        upload_dirs = {
            'i2v': Config.UPLOAD_I2V_DIR,
            'kf2v': Config.UPLOAD_KF2V_DIR,
            'i2i': Config.UPLOAD_I2I_DIR
        }
        
        base_dir = upload_dirs.get(task_type)
        if not base_dir:
            return jsonify({'error': '无效的任务类型'}), 400
        
        filepath = os.path.join(base_dir, api_key_hash, filename)
        if os.path.exists(filepath):
            return MediaHandler.serve_image(filepath, cache_days=7)
        
        return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@media_bp.route('/api/t2i-image/<api_key_hash>/<filename>')
def get_t2i_image(api_key_hash, filename):
    """获取文生图输出图片"""
    try:
        filepath = os.path.join(Config.OUTPUT_T2I_DIR, api_key_hash, filename)
        if os.path.exists(filepath):
            return MediaHandler.serve_image(filepath, cache_days=7)
        return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@media_bp.route('/api/i2i-image/<api_key_hash>/<filename>')
def get_i2i_image(api_key_hash, filename):
    """获取图生图输出图片"""
    try:
        filepath = os.path.join(Config.OUTPUT_I2I_DIR, api_key_hash, filename)
        if os.path.exists(filepath):
            return MediaHandler.serve_image(filepath, cache_days=7)
        return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 视频服务 ==========

@media_bp.route('/api/video/<task_type>/<api_key_hash>/<filename>')
def get_video(task_type, api_key_hash, filename):
    """获取视频文件（支持Range请求）
    
    task_type: i2v(图生视频), kf2v(首尾帧), t2v(文生视频), r2v(参考生视频)
    """
    try:
        # 根据任务类型选择目录
        dirs = {
            'i2v': Config.OUTPUT_I2V_DIR,
            'kf2v': Config.OUTPUT_KF2V_DIR,
            't2v': Config.OUTPUT_T2V_DIR
            # r2v 不在此处，需要特殊处理（区分上传视频和生成视频）
        }
        
        base_dir = dirs.get(task_type)
        if not base_dir:
            # 对于r2v，需要区分是上传的参考视频还是生成的视频
            if task_type == 'r2v':
                # 先尝试输出目录（生成的视频）
                output_path = os.path.join(Config.OUTPUT_R2V_DIR, api_key_hash, filename)
                if os.path.exists(output_path):
                    filepath = output_path
                else:
                    # 如果输出目录不存在，尝试上传目录（参考视频）
                    filepath = os.path.join(Config.UPLOAD_R2V_DIR, api_key_hash, filename)
            else:
                return jsonify({'error': '无效的任务类型'}), 400
        else:
            filepath = os.path.join(base_dir, api_key_hash, filename)
        
        return MediaHandler.serve_video_with_range(filepath)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@media_bp.route('/api/video-poster/<api_key_hash>/<task_id>')
def get_video_poster(api_key_hash, task_id):
    """获取视频封面图，如果不存在则自动生成"""
    try:
        cache_service = CacheService(api_key_hash)
        
        # 尝试获取或生成封面图
        poster_path = cache_service.get_or_generate_poster(task_id)
        
        if poster_path and os.path.exists(poster_path):
            # 返回封面图，带缓存头
            response = make_response(send_file(poster_path, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=2592000'  # 缓存30天
            response.headers['ETag'] = f'"{os.path.getmtime(poster_path)}"'
            return response
        else:
            # 封面图生成失败，返回空响应
            return '', 204
            
    except Exception as e:
        print(f"[ERROR] 获取视频封面失败: {e}")
        return '', 204


@media_bp.route('/api/r2v-ref-video-poster/<api_key_hash>/<filename>')
def get_r2v_ref_video_poster(api_key_hash, filename):
    """获取R2V参考视频的封面图，如果不存在则自动生成
    
    用于在任务历史中展示参考视频的截帧图
    """
    try:
        # 参考视频路径
        video_path = os.path.join(Config.UPLOAD_R2V_DIR, api_key_hash, filename)
        if not os.path.exists(video_path):
            return '', 204
        
        # 封面图路径：在参考视频同目录的posters子目录下
        poster_dir = os.path.join(Config.UPLOAD_R2V_DIR, api_key_hash, 'posters')
        os.makedirs(poster_dir, exist_ok=True)
        
        # 封面图文件名：使用视频文件名（去掉扩展名）+ .jpg
        video_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        poster_path = os.path.join(poster_dir, f'{video_name}.jpg')
        
        # 如果封面图不存在，生成它
        if not os.path.exists(poster_path):
            success = MediaHandler.generate_video_poster(video_path, poster_path)
            if not success:
                return '', 204
        
        # 返回封面图，带缓存头
        response = make_response(send_file(poster_path, mimetype='image/jpeg'))
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 缓存30天
        response.headers['ETag'] = f'"{os.path.getmtime(poster_path)}"'
        return response
        
    except Exception as e:
        print(f"[ERROR] 获取R2V参考视频封面失败: {e}")
        return '', 204


# ========== 音频服务 ==========

@media_bp.route('/api/upload-audio', methods=['POST'])
@require_auth
def upload_audio():
    """上传音频文件并获取OSS临时URL"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()

        if 'audio' not in request.files:
            return jsonify({'success': False, 'message': '没有上传音频文件'})

        file = request.files['audio']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})

        # 获取文件扩展名
        ext = ''
        if '.' in file.filename:
            ext = file.filename.rsplit('.', 1)[1].lower()

        # 验证音频格式
        if ext not in ['wav', 'mp3']:
            return jsonify({'success': False, 'message': '不支持的音频格式，仅支持 WAV 和 MP3'})

        # 生成新文件名
        import uuid
        import time
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        new_filename = f"{timestamp}_{unique_id}.{ext}"

        # 音频上传目录
        user_audio_dir = os.path.join(Config.UPLOAD_AUDIO_DIR, api_key_hash)
        os.makedirs(user_audio_dir, exist_ok=True)

        # 保存文件到本地临时目录
        filepath = os.path.join(user_audio_dir, new_filename)
        file.save(filepath)

        # 验证音频文件
        audio_service = AudioService(api_key)
        is_valid, error_msg = audio_service.validate_audio_file(filepath)

        if not is_valid:
            # 删除无效文件
            os.remove(filepath)
            return jsonify({'success': False, 'message': error_msg})

        # 上传到OSS并获取临时URL
        oss_url = audio_service.upload_audio_and_get_url(filepath, model_name="wanx-v1")

        if oss_url:
            return jsonify({
                'success': True,
                'filename': new_filename,
                'oss_url': oss_url,
                'message': '音频上传成功（有效期48小时）'
            })
        else:
            return jsonify({'success': False, 'message': '上传到OSS失败，请重试'})

    except Exception as e:
        print(f"[ERROR] 上传音频失败: {e}")
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})


@media_bp.route('/api/audio/<api_key_hash>/<filename>')
def get_audio(api_key_hash, filename):
    """获取本地音频文件"""
    try:
        filepath = os.path.join(Config.UPLOAD_AUDIO_DIR, api_key_hash, filename)
        if os.path.exists(filepath):
            # 根据扩展名返回正确的MIME类型
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'mp3'
            mime_types = {
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav'
            }
            mime_type = mime_types.get(ext, 'audio/mpeg')
            return send_file(filepath, mimetype=mime_type)
        return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 资产文件服务 ==========

@media_bp.route('/api/assets/<category>/<api_key_hash>/<filename>')
def get_asset(category, api_key_hash, filename):
    """获取资产文件"""
    try:
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        base_dir = category_dirs.get(category)
        if not base_dir:
            return jsonify({'error': '无效的资产分类'}), 400

        filepath = os.path.join(base_dir, api_key_hash, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404

        # 检测MIME类型
        if category == 'video':
            # 视频使用Range请求
            return MediaHandler.serve_video_with_range(filepath, 'video/mp4')
        else:
            # 图片直接返回
            return MediaHandler.serve_image(filepath, cache_days=7)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@media_bp.route('/api/assets/video-poster/<api_key_hash>/<poster_filename>')
def get_asset_video_poster(api_key_hash, poster_filename):
    """获取资产视频封面图"""
    try:
        poster_dir = os.path.join(Config.ASSETS_VIDEO_DIR, api_key_hash, 'posters')
        poster_path = os.path.join(poster_dir, poster_filename)
        
        if not os.path.exists(poster_path):
            # 尝试根据封面文件名找到视频并生成封面
            video_name = poster_filename.rsplit('.', 1)[0]
            video_dir = os.path.join(Config.ASSETS_VIDEO_DIR, api_key_hash)
            
            # 查找对应的视频文件
            video_path = None
            for ext in ['mp4', 'mov', 'avi', 'webm']:
                candidate = os.path.join(video_dir, f'{video_name}.{ext}')
                if os.path.exists(candidate):
                    video_path = candidate
                    break
            
            if video_path:
                MediaHandler.generate_video_poster(video_path, poster_path)
        
        if os.path.exists(poster_path):
            response = make_response(send_file(poster_path, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=2592000'  # 缓存30天
            response.headers['ETag'] = f'"{os.path.getmtime(poster_path)}"'
            return response
        else:
            # 封面图生成失败，返回404
            return jsonify({'error': '封面图不存在'}), 404
            
    except Exception as e:
        print(f"[ERROR] 获取资产视频封面失败: {e}")
        return jsonify({'error': str(e)}), 500


# ========== 其他服务 ==========

@media_bp.route('/api/video-effects', methods=['GET'])
def get_video_effects():
    """获取可用的视频特效列表"""
    try:
        effects_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'video_effects.json')

        if not os.path.exists(effects_file):
            return jsonify({'success': True, 'effects': []})

        with open(effects_file, 'r', encoding='utf-8') as f:
            effects_data = json.load(f)

        return jsonify({
            'success': True,
            'effects': effects_data.get('effects', [])
        })

    except Exception as e:
        print(f"[ERROR] 获取特效列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取特效列表失败: {str(e)}'})


@media_bp.route('/api/regenerate-task', methods=['POST'])
def regenerate_task():
    """重新生成任务 - 使用相同配置创建新任务 (图生视频)"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()

        if not api_key or not api_key_hash:
            return jsonify({'success': False, 'message': '请先输入API Key'})

        data = request.get_json()
        task_id = data.get('task_id')
        task_type = data.get('task_type', 'i2v')  # 默认为图生视频
        
        if not task_id:
            return jsonify({'success': False, 'message': '任务ID不能为空'})

        # 获取原始任务信息
        cache_service = CacheService(api_key_hash)
        
        # 根据任务类型获取任务
        if task_type == 't2i':
            original_task = cache_service.get_t2i_task(task_id)
        elif task_type == 'i2i':
            original_task = cache_service.get_i2i_task(task_id)
        elif task_type == 'kf2v':
            original_task = cache_service.get_kf2v_task(task_id)
        elif task_type == 't2v':
            original_task = cache_service.get_t2v_task(task_id)
        elif task_type == 'r2v':
            original_task = cache_service.get_r2v_task(task_id)
        else:  # i2v
            original_task = cache_service.get_task(task_id)
        
        if not original_task:
            return jsonify({'success': False, 'message': '找不到原始任务'})

        # 创建视频服务
        video_service = VideoService(api_key)

        # 获取原始任务的生成数量
        batch_total = original_task.get('batch_total', 1)
        
        # 根据任务类型创建新任务
        if task_type == 't2i':
            # 文生图任务需要批量创建
            created_tasks = []
            for i in range(batch_total):
                task_info = video_service.create_t2i_task(
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.5-t2i-preview'),
                    size=original_task.get('size', '1024*1024'),
                    n=original_task.get('n', 1),
                    negative_prompt=original_task.get('negative_prompt', ''),
                    prompt_extend=original_task.get('prompt_extend', True),
                    watermark=original_task.get('watermark', False)
                )
                if task_info:
                    # wan2.6-t2i是同步接口，直接返回图片，需要下载到本地
                    if task_info.get('model') == 'wan2.6-t2i' and task_info.get('task_status') == 'SUCCEEDED':
                        if task_info.get('image_urls'):
                            local_filenames = cache_service.download_t2i_images(task_info['task_id'], task_info['image_urls'])
                            if local_filenames:
                                local_image_urls = [f'/api/t2i-image/{api_key_hash}/{fn}' for fn in local_filenames]
                                task_info['local_image_urls'] = local_image_urls
                                task_info['local_filenames'] = local_filenames
                                print(f"[INFO] wan2.6-t2i图片已保存到本地: {local_filenames}")
                    created_tasks.append(task_info)
            
            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None
            
        elif task_type == 'i2i':
            # 获取参考图片路径
            reference_image_paths = []
            reference_image_filenames = []
            if original_task.get('reference_images'):
                for img_filename in original_task['reference_images']:
                    img_path = os.path.join(Config.UPLOAD_I2I_DIR, api_key_hash, img_filename)
                    if os.path.exists(img_path):
                        reference_image_paths.append(img_path)
                        reference_image_filenames.append(img_filename)
            else:
                # 如果原始任务没有reference_images字段，尝试从image_filenames字段获取
                # 这是为了兼容旧版本的任务数据
                image_filenames = original_task.get('image_filenames', [])
                for img_filename in image_filenames:
                    img_path = os.path.join(Config.UPLOAD_I2I_DIR, api_key_hash, img_filename)
                    if os.path.exists(img_path):
                        reference_image_paths.append(img_path)
                        reference_image_filenames.append(img_filename)
            
            # 图生图任务需要批量创建
            created_tasks = []
            # 获取原始任务的n参数（每个任务生成的图片数量）
            n_per_task = original_task.get('n', 1)
            for i in range(batch_total):
                task_info = video_service.create_i2i_task(
                    image_paths=reference_image_paths,
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.5-i2i-preview'),
                    size=original_task.get('size') if original_task.get('size') != '保持原图比例' else None,
                    n=n_per_task,
                    prompt_extend=original_task.get('prompt_extend', True),
                    negative_prompt=original_task.get('negative_prompt', '')
                )
                if task_info:
                    # 添加参考图片文件名到任务信息中
                    task_info['reference_images'] = reference_image_filenames
                    created_tasks.append(task_info)
            
            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None
            
        elif task_type == 'kf2v':
            # 获取首尾帧图片路径
            first_frame_path = os.path.join(Config.UPLOAD_KF2V_DIR, api_key_hash, original_task['first_frame_filename'])
            last_frame_path = os.path.join(Config.UPLOAD_KF2V_DIR, api_key_hash, original_task['last_frame_filename'])
            
            # 首尾帧任务需要批量创建
            created_tasks = []
            for i in range(batch_total):
                task_info = video_service.create_kf2v_task(
                    first_frame_path=first_frame_path,
                    last_frame_path=last_frame_path,
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.2-kf2v-flash'),
                    resolution=original_task.get('resolution', '480P'),
                    negative_prompt=original_task.get('negative_prompt', ''),
                    prompt_extend=original_task.get('prompt_extend', True)
                )
                if task_info:
                    created_tasks.append(task_info)
            
            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None
            
        elif task_type == 't2v':
            # 文生视频任务需要批量创建
            created_tasks = []
            for i in range(batch_total):
                task_info = video_service.create_t2v_task(
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.6-t2v'),
                    resolution=original_task.get('resolution', '720P'),
                    duration=int(original_task.get('duration', 5)),
                    audio=original_task.get('audio', False),
                    audio_url=original_task.get('audio_url', ''),
                    negative_prompt=original_task.get('negative_prompt', ''),
                    shot_type=original_task.get('shot_type', 'single')
                )
                if task_info:
                    created_tasks.append(task_info)

            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None

        elif task_type == 'r2v':
            # 参考生视频任务需要批量创建
            reference_video_filenames = original_task.get('reference_video_filenames', [])
            reference_video_paths = []
            for filename in reference_video_filenames:
                video_path = os.path.join(Config.UPLOAD_R2V_DIR, api_key_hash, filename)
                if os.path.exists(video_path):
                    reference_video_paths.append(video_path)
            
            created_tasks = []
            for i in range(batch_total):
                task_info = video_service.create_r2v_task(
                    reference_video_paths=reference_video_paths,
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.6-r2v'),
                    size=original_task.get('size', '1280*720'),
                    duration=int(original_task.get('duration', 5)),
                    shot_type=original_task.get('shot_type', 'single'),
                    negative_prompt=original_task.get('negative_prompt', ''),
                    watermark=original_task.get('watermark', False),
                    audio=original_task.get('audio', True)
                )
                if task_info:
                    created_tasks.append(task_info)

            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None

        else:  # i2v
            # 图生视频任务需要批量创建
            created_tasks = []
            image_path = os.path.join(Config.UPLOAD_I2V_DIR, api_key_hash, original_task['image_filename'])
            for i in range(batch_total):
                task_info = video_service.create_task(
                    image_path=image_path,
                    prompt=original_task.get('prompt', ''),
                    model=original_task.get('model', 'wan2.6-i2v'),
                    resolution=original_task.get('resolution', '720P'),
                    duration=int(original_task.get('duration', 5)),
                    audio_url=original_task.get('audio_url', ''),
                    negative_prompt=original_task.get('negative_prompt', ''),
                    prompt_extend=original_task.get('prompt_extend', True),
                    shot_type=original_task.get('shot_type', 'single'),
                    watermark=original_task.get('watermark', False),
                    audio=original_task.get('audio', False)  # 修复：默认值应为False而不是True
                )
                if task_info:
                    created_tasks.append(task_info)
            
            # 使用第一个任务作为返回任务
            task_info = created_tasks[0] if created_tasks else None

        if task_info:
            # 保存所有创建的任务信息
            saved_tasks = []
            
            # 为批量任务生成新的批次ID
            import uuid
            new_batch_id = str(uuid.uuid4()) if batch_total > 1 else None
            
            for i, task in enumerate(created_tasks):
                # 添加任务类型信息
                task['task_type'] = task_type
                
                # 添加批次信息
                task['batch_id'] = new_batch_id
                task['batch_index'] = i + 1
                task['batch_total'] = batch_total

                # 保存任务信息到对应的任务类型
                if task_type == 't2i':
                    cache_service.add_t2i_task(task)
                elif task_type == 'i2i':
                    # 添加参考图片文件名和URL（如果还没有的话）
                    if (original_task.get('reference_images') or original_task.get('image_filenames')) and not task.get('reference_image_urls'):
                        # 优先使用reference_images，如果没有则使用image_filenames
                        ref_images = original_task.get('reference_images') or original_task.get('image_filenames', [])
                        # 添加参考图片URL到任务信息中
                        reference_image_urls = []
                        for filename in ref_images:
                            reference_image_urls.append(f'/api/image/i2i/{api_key_hash}/{filename}')
                        task['reference_images'] = ref_images
                        task['reference_image_urls'] = reference_image_urls
                    cache_service.add_i2i_task(task)

                elif task_type == 'kf2v':
                    # 添加首尾帧文件名
                    task['first_frame_filename'] = original_task['first_frame_filename']
                    task['last_frame_filename'] = original_task['last_frame_filename']
                    cache_service.add_kf2v_task(task)
                elif task_type == 't2v':
                    # 添加文生视频任务
                    cache_service.add_t2v_task(task)
                elif task_type == 'r2v':
                    # 添加参考生视频任务
                    task['reference_video_filenames'] = original_task.get('reference_video_filenames', [])
                    cache_service.add_r2v_task(task)
                else:  # i2v
                    task['image_filename'] = original_task['image_filename']
                    cache_service.add_task(task)
                
                saved_tasks.append(task)

            # 添加图片URL到返回数据（仅适用于i2v，使用第一个任务）
            if task_type == 'i2v':
                saved_tasks[0]['image_url'] = f'/api/image/i2v/{api_key_hash}/{original_task["image_filename"]}'

            print(f"[INFO] 重新生成任务成功: {saved_tasks[0]['task_id']}")
            
            return jsonify({
                'success': True,
                'tasks': saved_tasks,
                'message': '重新生成任务'
            })
        else:
            return jsonify({'success': False, 'message': '重新生成任务失败'})

    except Exception as e:
        print(f"[ERROR] 重新生成任务失败: {e}")
        return jsonify({'success': False, 'message': f'重新生成任务失败: {str(e)}'})

