"""项目管理模块蓝图"""
from flask import Blueprint, request, jsonify
from core.services.project_service import ProjectService
from core.utils.session_helper import get_api_key_hash, require_auth

project_bp = Blueprint('project', __name__)


@project_bp.route('/api/assets/projects', methods=['GET'])
@require_auth
def get_projects():
    """获取项目列表"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        projects = project_service.get_projects()
        return jsonify({'success': True, 'projects': projects})
    
    except Exception as e:
        print(f"[ERROR] 获取项目列表失败: {e}")
        return jsonify({'success': False, 'message': f'获取失败: {str(e)}'})


@project_bp.route('/api/assets/projects', methods=['POST'])
@require_auth
def create_project():
    """创建项目"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        project_name = data.get('name', '').strip()
        
        success, result = project_service.create_project(project_name)
        
        if success:
            return jsonify({'success': True, 'project': result})
        else:
            return jsonify({'success': False, 'message': result})
    
    except Exception as e:
        print(f"[ERROR] 创建项目失败: {e}")
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>', methods=['DELETE'])
@require_auth
def delete_project(project_name):
    """删除项目"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        success, message = project_service.delete_project(project_name)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        print(f"[ERROR] 删除项目失败: {e}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>', methods=['PUT'])
@require_auth
def rename_project(project_name):
    """重命名项目"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        new_name = data.get('name', '').strip()
        
        success, message = project_service.rename_project(project_name, new_name)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        print(f"[ERROR] 重命名项目失败: {e}")
        return jsonify({'success': False, 'message': f'重命名失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>/episodes', methods=['POST'])
@require_auth
def add_episode(project_name):
    """添加分集"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        episode_name = data.get('name', '').strip()
        
        success, result = project_service.add_episode(project_name, episode_name)
        
        if success:
            return jsonify({'success': True, 'episodes': result})
        else:
            return jsonify({'success': False, 'message': result})
    
    except Exception as e:
        print(f"[ERROR] 添加分集失败: {e}")
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>/episodes/<episode_name>', methods=['DELETE'])
@require_auth
def delete_episode(project_name, episode_name):
    """删除分集"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        success, result = project_service.delete_episode(project_name, episode_name)
        
        if success:
            return jsonify({'success': True, 'message': '删除成功', 'episodes': result})
        else:
            return jsonify({'success': False, 'message': result})
    
    except Exception as e:
        print(f"[ERROR] 删除分集失败: {e}")
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>/episodes/<episode_name>', methods=['PUT'])
@require_auth
def rename_episode(project_name, episode_name):
    """重命名分集"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        new_name = data.get('name', '').strip()
        
        success, result = project_service.rename_episode(project_name, episode_name, new_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'重命名成功，已更新 {result.get("updated_count", 0)} 个资产',
                'episodes': result.get('episodes', [])
            })
        else:
            return jsonify({'success': False, 'message': result})
    
    except Exception as e:
        print(f"[ERROR] 重命名分集失败: {e}")
        return jsonify({'success': False, 'message': f'重命名失败: {str(e)}'})


@project_bp.route('/api/assets/projects/<project_name>/asset-count', methods=['GET'])
@require_auth
def get_project_asset_count(project_name):
    """获取项目关联的资产数量"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        count = project_service.get_project_asset_count(project_name)
        return jsonify({'success': True, 'count': count})
    
    except Exception as e:
        print(f"[ERROR] 获取项目资产数量失败: {e}")
        return jsonify({'success': False, 'message': f'获取失败: {str(e)}', 'count': 0})


@project_bp.route('/api/assets/update-tags', methods=['POST'])
@require_auth
def update_asset_tags():
    """更新单个资产的标签"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        category = data.get('category')
        filename = data.get('filename')
        project = data.get('project', '')
        episode = data.get('episode', '')
        
        if not category or not filename:
            return jsonify({'success': False, 'message': '缺少参数'})
        
        success, message = project_service.update_asset_tags(category, filename, project, episode)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        print(f"[ERROR] 更新资产标签失败: {e}")
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})


@project_bp.route('/api/assets/batch-tags', methods=['POST'])
@require_auth
def batch_update_tags():
    """批量更新资产标签"""
    try:
        api_key_hash = get_api_key_hash()
        project_service = ProjectService(api_key_hash)
        
        data = request.get_json()
        assets = data.get('assets', [])
        project = data.get('project', '')
        episode = data.get('episode', '')
        
        if not assets:
            return jsonify({'success': False, 'message': '请选择要更新的资产'})
        
        success, message = project_service.batch_update_tags(assets, project, episode)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
    
    except Exception as e:
        print(f"[ERROR] 批量更新标签失败: {e}")
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})
