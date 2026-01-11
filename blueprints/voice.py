"""语音复刻模块蓝图"""
import os
import uuid
import time
from flask import Blueprint, render_template, request, jsonify, session
from config import Config
from services.voice_service import VoiceService
from services.cache_service import CacheService
from services.audio_service import AudioService
from core.services.file_service import FileService
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.utils.logger import setup_logger

logger = setup_logger(__name__)

voice_bp = Blueprint('voice', __name__)


@voice_bp.route('/voice-clone')
def voice_clone_page():
    """语音复刻页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('voice_clone.html')


@voice_bp.route('/api/voice/upload-audio', methods=['POST'])
@require_auth
def upload_voice_audio():
    """上传语音样本
    
    上传用于语音复刻的音频样本文件
    """
    try:
        api_key_hash = get_api_key_hash()
        
        if 'audio' not in request.files:
            return jsonify({'success': False, 'message': '没有上传文件'})
        
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
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        new_filename = f"{timestamp}_{unique_id}.{ext}"
        
        # 语音样本上传目录
        user_voice_dir = os.path.join(Config.UPLOAD_VOICE_DIR, api_key_hash)
        os.makedirs(user_voice_dir, exist_ok=True)
        
        # 保存文件
        filepath = os.path.join(user_voice_dir, new_filename)
        file.save(filepath)
        
        logger.info(f"语音样本已上传: {filepath}")
        
        return jsonify({
            'success': True,
            'filename': new_filename,
            'url': f'/api/voice/audio/{api_key_hash}/{new_filename}'
        })
    
    except Exception as e:
        logger.error(f"上传语音样本失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})


@voice_bp.route('/api/voice/audio/<api_key_hash>/<filename>')
def get_voice_audio(api_key_hash, filename):
    """获取语音样本或合成音频文件"""
    from flask import send_file
    try:
        # 先尝试语音样本目录
        filepath = os.path.join(Config.UPLOAD_VOICE_DIR, api_key_hash, filename)
        
        # 如果样本目录不存在，尝试输出目录
        if not os.path.exists(filepath):
            filepath = os.path.join(Config.OUTPUT_VOICE_DIR, api_key_hash, filename)
        
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
        logger.error(f"获取语音文件失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@voice_bp.route('/api/voice/create', methods=['POST'])
@require_auth
def create_voice():
    """创建音色（复刻）
    
    创建音色是异步任务，需要轮询查询状态
    """
    try:
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        audio_filename = data.get('audio_filename')
        prefix = data.get('prefix', '').lower()
        name = data.get('name', '')
        
        if not audio_filename:
            return jsonify({'success': False, 'message': '请先上传语音样本'})
        
        # 验证前缀格式
        if not prefix:
            return jsonify({'success': False, 'message': '请输入音色前缀'})
        
        if len(prefix) >= 10:
            return jsonify({'success': False, 'message': '前缀必须小于10个字符'})
        
        if not prefix.isalnum():
            return jsonify({'success': False, 'message': '前缀只能包含小写字母和数字'})
        
        # 验证音频文件存在
        audio_path = os.path.join(Config.UPLOAD_VOICE_DIR, api_key_hash, audio_filename)
        if not os.path.exists(audio_path):
            return jsonify({'success': False, 'message': '音频文件不存在'})
        
        # 使用 AudioService 上传音频到 OSS 临时存储
        api_key = get_api_key()
        audio_service = AudioService(api_key)
        
        # 验证音频文件
        is_valid, error_msg = audio_service.validate_audio_file(audio_path)
        if not is_valid:
            return jsonify({'success': False, 'message': error_msg})
        
        # 上传到 OSS 获取临时 URL
        audio_url = audio_service.upload_audio_and_get_url(audio_path, model_name="cosyvoice-v1")
        if not audio_url:
            return jsonify({'success': False, 'message': '上传音频到云端失败'})
        
        logger.info(f"音频OSS URL: {audio_url}")
        
        voice_service = VoiceService(api_key)
        cache_service = CacheService(api_key_hash)
        
        result = voice_service.create_voice(
            audio_url=audio_url,
            prefix=prefix,
            target_model=data.get('model', 'cosyvoice-v3-plus')
        )
        
        if result:
            # 添加额外信息
            result['name'] = name
            result['audio_filename'] = audio_filename
            
            # 保存到本地缓存
            cache_service.add_voice(result)
            
            logger.info(f"创建音色成功: {result['voice_id']}")
            
            return jsonify({
                'success': True,
                'voice': result
            })
        else:
            return jsonify({'success': False, 'message': '创建音色失败'})
    
    except Exception as e:
        logger.error(f"创建音色失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'})


@voice_bp.route('/api/voice/status/<voice_id>', methods=['GET'])
@require_auth
def get_voice_status(voice_id):
    """查询音色状态
    
    状态值：
    - OK: 音色就绪，可用于合成
    - DEPLOYING: 处理中
    - UNDEPLOYED: 处理失败
    """
    try:
        api_key_hash = get_api_key_hash()
        
        voice_service = VoiceService(get_api_key())
        cache_service = CacheService(api_key_hash)
        
        result = voice_service.query_voice_status(voice_id)
        
        if result:
            # 更新本地缓存
            cache_service.update_voice(voice_id, {
                'status': result.get('status'),
                'updated_at': result.get('updated_at')
            })
            return jsonify({'success': True, 'voice': result})
        else:
            return jsonify({'success': False, 'message': '查询失败'})
    
    except Exception as e:
        logger.error(f"查询音色状态失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'查询失败: {str(e)}'})


@voice_bp.route('/api/voice/list', methods=['GET'])
@require_auth
def list_voices():
    """获取音色列表"""
    try:
        api_key_hash = get_api_key_hash()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        cache_service = CacheService(api_key_hash)
        voices, total, has_more = cache_service.get_voices_paginated(page, limit)
        
        return jsonify({
            'success': True,
            'voices': voices,
            'page': page,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        logger.error(f"获取音色列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取列表失败: {str(e)}'})


@voice_bp.route('/api/voice/delete/<voice_id>', methods=['DELETE'])
@require_auth
def delete_voice(voice_id):
    """删除音色"""
    try:
        api_key_hash = get_api_key_hash()
        
        voice_service = VoiceService(get_api_key())
        cache_service = CacheService(api_key_hash)
        
        # 从云端删除
        if voice_service.delete_voice(voice_id):
            # 从本地缓存删除
            cache_service.delete_voice(voice_id)
            logger.info(f"音色已删除: {voice_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '删除失败'})
    
    except Exception as e:
        logger.error(f"删除音色失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


@voice_bp.route('/api/voice/synthesize', methods=['POST'])
@require_auth
def synthesize_speech():
    """使用音色合成语音"""
    try:
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        
        voice_id = data.get('voice_id')
        text = data.get('text', '').strip()
        volume = data.get('volume', 50)  # 默认50
        speech_rate = data.get('speech_rate', 1.0)  # 默认1.0
        pitch_rate = data.get('pitch_rate', 1.0)  # 默认1.0
        
        if not voice_id:
            return jsonify({'success': False, 'message': '请选择音色'})
        
        if not text:
            return jsonify({'success': False, 'message': '请输入要合成的文本'})
        
        if len(text) > 1000:
            return jsonify({'success': False, 'message': '文本长度不能超过1000字符'})
        
        # 参数验证
        volume = max(0, min(100, int(volume)))
        speech_rate = max(0.5, min(2.0, float(speech_rate)))
        pitch_rate = max(0.5, min(2.0, float(pitch_rate)))
        
        voice_service = VoiceService(get_api_key())
        cache_service = CacheService(api_key_hash)
        
        # 生成任务ID和输出路径
        task_id = f"synth_{uuid.uuid4().hex[:16]}"
        output_dir = cache_service.get_output_voice_dir()
        output_path = os.path.join(output_dir, f"{task_id}.mp3")
        
        result = voice_service.synthesize_speech(
            voice_id=voice_id,
            text=text,
            output_path=output_path,
            volume=volume,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate
        )
        
        if result:
            task_info = {
                'task_id': task_id,
                'voice_id': voice_id,
                'text': text,
                'task_status': 'SUCCEEDED',
                'output_filename': f"{task_id}.mp3"
            }
            cache_service.add_voice_task(task_info)
            
            logger.info(f"语音合成成功: {task_id}")
            
            return jsonify({
                'success': True,
                'task': task_info,
                'audio_url': f"/api/voice/audio/{api_key_hash}/{task_id}.mp3"
            })
        else:
            return jsonify({'success': False, 'message': '语音合成失败'})
    
    except Exception as e:
        logger.error(f"语音合成失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'合成失败: {str(e)}'})


@voice_bp.route('/api/voice/tasks', methods=['GET'])
@require_auth
def get_voice_tasks():
    """获取语音合成任务列表"""
    try:
        api_key_hash = get_api_key_hash()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        cache_service = CacheService(api_key_hash)
        tasks, total, has_more = cache_service.get_voice_tasks_paginated(page, limit)
        
        # 为每个任务添加音频URL
        for task in tasks:
            if task.get('output_filename'):
                task['audio_url'] = f"/api/voice/audio/{api_key_hash}/{task['output_filename']}"
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'page': page,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        logger.error(f"获取语音任务列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'})

