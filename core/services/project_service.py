"""项目管理服务"""
import os
import json
import time
from config import Config


class ProjectService:
    """项目管理服务
    
    负责项目和分集的管理
    """
    
    def __init__(self, api_key_hash):
        """初始化项目服务
        
        Args:
            api_key_hash: 用户API Key哈希值
        """
        self.api_key_hash = api_key_hash
        self.projects_dir = os.path.join(Config.CACHE_DIR, 'projects')
        os.makedirs(self.projects_dir, exist_ok=True)
        self.projects_file = os.path.join(self.projects_dir, f'{api_key_hash}_projects.json')
    
    # ========== 项目管理 ==========
    
    def get_projects(self):
        """获取项目列表
        
        Returns:
            项目列表
        """
        return self._load_projects()
    
    def create_project(self, project_name):
        """创建项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            (success, result) - result为新项目信息或错误消息
        """
        if not project_name or not project_name.strip():
            return False, '项目名称不能为空'
        
        project_name = project_name.strip()
        projects = self._load_projects()
        
        # 检查是否已存在
        if any(p['name'] == project_name for p in projects):
            return False, '项目已存在'
        
        # 添加新项目
        new_project = {
            'name': project_name,
            'episodes': [],
            'created_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        projects.append(new_project)
        self._save_projects(projects)
        
        return True, new_project
    
    def delete_project(self, project_name):
        """删除项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            (success, message)
        """
        projects = self._load_projects()
        projects = [p for p in projects if p['name'] != project_name]
        self._save_projects(projects)
        
        return True, '删除成功'
    
    def rename_project(self, old_name, new_name):
        """重命名项目
        
        Args:
            old_name: 原项目名称
            new_name: 新项目名称
            
        Returns:
            (success, message)
        """
        if not new_name or not new_name.strip():
            return False, '项目名称不能为空'
        
        new_name = new_name.strip()
        projects = self._load_projects()
        
        # 检查新名称是否已存在
        if any(p['name'] == new_name for p in projects):
            return False, '项目名称已存在'
        
        # 找到并重命名项目
        found = False
        for p in projects:
            if p['name'] == old_name:
                p['name'] = new_name
                found = True
                break
        
        if not found:
            return False, '项目不存在'
        
        self._save_projects(projects)
        
        # 更新所有使用该项目的资产元数据
        updated_count = self._update_asset_project_name(old_name, new_name)
        
        return True, f'重命名成功，已更新 {updated_count} 个资产'
    
    # ========== 分集管理 ==========
    
    def add_episode(self, project_name, episode_name):
        """添加分集
        
        Args:
            project_name: 项目名称
            episode_name: 分集名称
            
        Returns:
            (success, result) - result为分集列表或错误消息
        """
        if not episode_name or not episode_name.strip():
            return False, '分集名称不能为空'
        
        episode_name = episode_name.strip()
        projects = self._load_projects()
        
        for project in projects:
            if project['name'] == project_name:
                if episode_name in project.get('episodes', []):
                    return False, '分集已存在'
                project.setdefault('episodes', []).append(episode_name)
                self._save_projects(projects)
                return True, project['episodes']
        
        return False, '项目不存在'
    
    def delete_episode(self, project_name, episode_name):
        """删除分集
        
        Args:
            project_name: 项目名称
            episode_name: 分集名称
            
        Returns:
            (success, result) - result为分集列表或错误消息
        """
        projects = self._load_projects()
        
        for project in projects:
            if project['name'] == project_name:
                episodes = project.get('episodes', [])
                if episode_name in episodes:
                    episodes.remove(episode_name)
                    project['episodes'] = episodes
                    self._save_projects(projects)
                    
                    # 清空使用该分集的资产的分集标签
                    self._clear_asset_episode(project_name, episode_name)
                    
                    return True, project['episodes']
                else:
                    return False, '分集不存在'
        
        return False, '项目不存在'
    
    def rename_episode(self, project_name, old_name, new_name):
        """重命名分集
        
        Args:
            project_name: 项目名称
            old_name: 原分集名称
            new_name: 新分集名称
            
        Returns:
            (success, result) - result为分集列表或错误消息
        """
        if not new_name or not new_name.strip():
            return False, '分集名称不能为空'
        
        new_name = new_name.strip()
        projects = self._load_projects()
        
        for project in projects:
            if project['name'] == project_name:
                episodes = project.get('episodes', [])
                
                if new_name in episodes:
                    return False, '分集名称已存在'
                
                if old_name in episodes:
                    idx = episodes.index(old_name)
                    episodes[idx] = new_name
                    project['episodes'] = episodes
                    self._save_projects(projects)
                    
                    # 更新使用该分集的资产的分集标签
                    updated_count = self._update_asset_episode_name(project_name, old_name, new_name)
                    
                    return True, {'episodes': project['episodes'], 'updated_count': updated_count}
                else:
                    return False, '分集不存在'
        
        return False, '项目不存在'
    
    # ========== 资产关联 ==========
    
    def update_asset_tags(self, category, filename, project, episode):
        """更新资产标签
        
        Args:
            category: 资产分类
            filename: 文件名
            project: 项目名称
            episode: 分集名称
            
        Returns:
            (success, message)
        """
        # 读取现有元数据
        meta_data = self._load_asset_metadata(category, filename)
        
        # 更新标签
        meta_data['project'] = project
        meta_data['episode'] = episode
        meta_data['filename'] = filename
        meta_data['category'] = category
        
        # 保存元数据
        success = self._save_asset_metadata(category, filename, meta_data)
        if not success:
            return False, '保存元数据失败'
        
        # 如果项目/分集不存在，自动添加到项目列表
        if project:
            self._ensure_project_exists(project, episode)
        
        return True, '标签更新成功'
    
    def batch_update_tags(self, assets, project, episode):
        """批量更新资产标签
        
        Args:
            assets: 资产列表 [{category, filename}, ...]
            project: 项目名称
            episode: 分集名称
            
        Returns:
            (success, message)
        """
        updated_count = 0
        
        for asset in assets:
            category = asset.get('category')
            filename = asset.get('filename')
            
            if not category or not filename:
                continue
            
            # 读取现有元数据
            meta_data = self._load_asset_metadata(category, filename)
            
            # 更新标签
            meta_data['project'] = project
            meta_data['episode'] = episode
            meta_data['filename'] = filename
            meta_data['category'] = category
            
            # 保存元数据
            if self._save_asset_metadata(category, filename, meta_data):
                updated_count += 1
        
        # 如果项目/分集不存在，自动添加到项目列表
        if project:
            self._ensure_project_exists(project, episode)
        
        return True, f'成功更新 {updated_count} 个资产的标签'
    
    def get_project_asset_count(self, project_name):
        """获取项目关联的资产数量
        
        Args:
            project_name: 项目名称
            
        Returns:
            资产数量
        """
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        count = 0
        for cat, base_dir in category_dirs.items():
            user_dir = os.path.join(base_dir, self.api_key_hash)
            if not os.path.exists(user_dir):
                continue
            
            for filename in os.listdir(user_dir):
                if not filename.endswith('.meta.json'):
                    continue
                
                meta_path = os.path.join(user_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    if meta.get('project') == project_name:
                        count += 1
                except:
                    pass
        
        return count
    
    # ========== 私有方法 ==========
    
    def _load_projects(self):
        """加载项目列表"""
        if os.path.exists(self.projects_file):
            try:
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_projects(self, projects):
        """保存项目列表"""
        with open(self.projects_file, 'w', encoding='utf-8') as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
    
    def _get_asset_dir(self, category):
        """获取资产目录"""
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        base_dir = category_dirs.get(category)
        if not base_dir:
            return None
        return os.path.join(base_dir, self.api_key_hash)
    
    def _load_asset_metadata(self, category, filename):
        """加载资产元数据"""
        user_dir = self._get_asset_dir(category)
        if not user_dir:
            return {}
        
        meta_path = os.path.join(user_dir, filename + '.meta.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_asset_metadata(self, category, filename, meta_data):
        """保存资产元数据"""
        user_dir = self._get_asset_dir(category)
        if not user_dir:
            return False
        
        meta_path = os.path.join(user_dir, filename + '.meta.json')
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def _update_asset_project_name(self, old_name, new_name):
        """更新资产的项目名称"""
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        updated_count = 0
        for cat, base_dir in category_dirs.items():
            user_dir = os.path.join(base_dir, self.api_key_hash)
            if not os.path.exists(user_dir):
                continue
            
            for filename in os.listdir(user_dir):
                if not filename.endswith('.meta.json'):
                    continue
                
                meta_path = os.path.join(user_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    if meta.get('project') == old_name:
                        meta['project'] = new_name
                        with open(meta_path, 'w', encoding='utf-8') as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                        updated_count += 1
                except:
                    pass
        
        return updated_count
    
    def _clear_asset_episode(self, project_name, episode_name):
        """清空资产的分集标签"""
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        for cat, base_dir in category_dirs.items():
            user_dir = os.path.join(base_dir, self.api_key_hash)
            if not os.path.exists(user_dir):
                continue
            
            for filename in os.listdir(user_dir):
                if not filename.endswith('.meta.json'):
                    continue
                
                meta_path = os.path.join(user_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    if meta.get('project') == project_name and meta.get('episode') == episode_name:
                        meta['episode'] = ''
                        with open(meta_path, 'w', encoding='utf-8') as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                except:
                    pass
    
    def _update_asset_episode_name(self, project_name, old_name, new_name):
        """更新资产的分集名称"""
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        updated_count = 0
        for cat, base_dir in category_dirs.items():
            user_dir = os.path.join(base_dir, self.api_key_hash)
            if not os.path.exists(user_dir):
                continue
            
            for filename in os.listdir(user_dir):
                if not filename.endswith('.meta.json'):
                    continue
                
                meta_path = os.path.join(user_dir, filename)
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    if meta.get('project') == project_name and meta.get('episode') == old_name:
                        meta['episode'] = new_name
                        with open(meta_path, 'w', encoding='utf-8') as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                        updated_count += 1
                except:
                    pass
        
        return updated_count
    
    def _ensure_project_exists(self, project_name, episode_name=None):
        """确保项目存在，不存在则自动创建"""
        projects = self._load_projects()
        project_exists = False
        
        for p in projects:
            if p['name'] == project_name:
                project_exists = True
                if episode_name and episode_name not in p.get('episodes', []):
                    p.setdefault('episodes', []).append(episode_name)
                break
        
        if not project_exists:
            new_project = {
                'name': project_name,
                'episodes': [episode_name] if episode_name else [],
                'created_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            projects.append(new_project)
        
        self._save_projects(projects)
