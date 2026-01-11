"""任务管理服务

由于TaskService涉及大量业务逻辑和VideoService、CacheService的深度集成，
建议在实际使用时直接调用VideoService和CacheService，
或者在后续根据实际需求逐步抽象通用逻辑。

本文件作为占位符，为未来的统一任务管理预留接口。
"""

from services.video_service import VideoService
from services.cache_service import CacheService


class TaskService:
    """任务管理服务
    
    负责所有任务类型的统一管理逻辑
    
    注意：当前版本保持与原有VideoService和CacheService的兼容性
    """
    
    def __init__(self, api_key, api_key_hash):
        """初始化任务服务
        
        Args:
            api_key: API Key
            api_key_hash: API Key哈希值
        """
        self.api_key = api_key
        self.api_key_hash = api_key_hash
        self.video_service = VideoService(api_key)
        self.cache_service = CacheService(api_key_hash)
    
    def get_cache_service(self):
        """获取缓存服务实例"""
        return self.cache_service
    
    def get_video_service(self):
        """获取视频服务实例"""
        return self.video_service
    
    # 未来可以在这里添加统一的任务管理方法
    # 例如：
    # - create_tasks(task_type, task_config, batch_count)
    # - get_task_status(task_id, task_type)
    # - get_tasks_paginated(task_type, page, limit)
    # - regenerate_task(task_id, task_type)
