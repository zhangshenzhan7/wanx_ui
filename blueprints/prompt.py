"""提示词优化模块蓝图"""
import os
from flask import Blueprint, request, jsonify
from config import Config
from core.utils.session_helper import get_api_key, get_api_key_hash, require_auth
from core.services.prompt_service import PromptService

prompt_bp = Blueprint('prompt', __name__)


@prompt_bp.route('/api/optimize-prompt', methods=['POST'])
@require_auth
def optimize_prompt():
    """优化提示词 - 根据任务类型分发到不同的优化函数"""
    try:
        api_key = get_api_key()
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        original_prompt = data.get('prompt', '').strip()
        task_type = data.get('task_type', 'video')  # video(图生视频), image(文生图), text2video(文生视频)
        image_filename = data.get('image_filename', '')  # 图片文件名（用于图生视频）

        if not original_prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'})

        # 创建提示词服务
        prompt_service = PromptService(api_key)
        
        # 准备额外上下文
        extra_context = None
        if task_type == 'video' and image_filename:
            # 构建图片路径
            image_path = os.path.join(Config.UPLOAD_I2V_DIR, api_key_hash, image_filename)
            if os.path.exists(image_path):
                extra_context = {'image_path': image_path}
        
        # 调用优化服务
        return prompt_service.optimize_prompt(original_prompt, task_type, extra_context)

    except Exception as e:
        print(f"优化提示词失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'优化失败: {str(e)}'
        })
