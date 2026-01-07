"""认证模块蓝图"""
from flask import Blueprint, render_template, request, jsonify, session
from services.video_service import VideoService
from services.cache_service import CacheService
from core.utils.session_helper import generate_api_key_hash

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """首页 - API Key输入页面"""
    if 'api_key_hash' in session:
        return render_template('workspace.html')
    return render_template('index.html')


@auth_bp.route('/api/verify-key', methods=['POST'])
def verify_key():
    """验证API Key"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({'success': False, 'message': 'API Key不能为空'})

        # 验证API Key（通过调用一个简单的API）
        video_service = VideoService(api_key)
        if not video_service.verify_api_key():
            return jsonify({'success': False, 'message': 'API Key无效，请检查后重试'})

        # 生成API Key哈希
        api_key_hash = generate_api_key_hash(api_key)

        # 保存到session
        session['api_key'] = api_key
        session['api_key_hash'] = api_key_hash

        # 初始化用户缓存
        cache_service = CacheService(api_key_hash)
        cache_service.init_user_cache()

        return jsonify({'success': True, 'message': 'API Key验证成功'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败: {str(e)}'})


@auth_bp.route('/workspace')
def workspace():
    """工作区页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('workspace.html')


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """退出登录"""
    session.clear()
    return jsonify({'success': True})
