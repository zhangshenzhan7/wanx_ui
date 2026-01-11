import os
import json
import hashlib
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import requests
import time
from config import Config


class CacheService:
    """缓存服务类，管理用户数据和视频缓存"""
    
    # 类级别的HTTP会话池(用于视频下载)
    _session = None

    def __init__(self, api_key_hash: str):
        """初始化缓存服务
        
        Args:
            api_key_hash: API Key的哈希值，用于用户隔离
        """
        self.api_key_hash = api_key_hash
        
        # 初始化HTTP会话(连接池复用)
        if CacheService._session is None:
            CacheService._session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=30,
                max_retries=3
            )
            CacheService._session.mount('http://', adapter)
            CacheService._session.mount('https://', adapter)

    def get_user_cache_file(self) -> str:
        """获取用户缓存文件路径 (deprecated)"""
        return os.path.join(Config.CACHE_DIR, f'user_{self.api_key_hash}.json')

    # ========== 上传目录获取方法 ==========
    
    def get_upload_i2v_dir(self) -> str:
        """获取图生视频上传图片目录"""
        upload_dir = os.path.join(Config.UPLOAD_I2V_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_upload_kf2v_dir(self) -> str:
        """获取首尾帧上传图片目录"""
        upload_dir = os.path.join(Config.UPLOAD_KF2V_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_upload_i2i_dir(self) -> str:
        """获取图生图参考图片目录"""
        upload_dir = os.path.join(Config.UPLOAD_I2I_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_upload_r2v_dir(self) -> str:
        """获取参考生视频上传视频目录"""
        upload_dir = os.path.join(Config.UPLOAD_R2V_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_upload_audio_dir(self) -> str:
        """获取音频文件目录"""
        upload_dir = os.path.join(Config.UPLOAD_AUDIO_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    # ========== 输出目录获取方法 ==========
    
    def get_output_i2v_dir(self) -> str:
        """获取图生视频输出目录"""
        output_dir = os.path.join(Config.OUTPUT_I2V_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def get_output_kf2v_dir(self) -> str:
        """获取首尾帧输出目录"""
        output_dir = os.path.join(Config.OUTPUT_KF2V_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def get_output_t2i_dir(self) -> str:
        """获取文生图输出目录"""
        output_dir = os.path.join(Config.OUTPUT_T2I_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def get_output_i2i_dir(self) -> str:
        """获取图生图输出目录"""
        output_dir = os.path.join(Config.OUTPUT_I2I_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def get_output_r2v_dir(self) -> str:
        """获取参考生视频输出目录"""
        output_dir = os.path.join(Config.OUTPUT_R2V_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_output_t2v_dir(self) -> str:
        """获取文生视频输出目录"""
        output_dir = os.path.join(Config.OUTPUT_T2V_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    # ========== 兼容旧方法 (deprecated) ==========
    
    def get_user_video_dir(self) -> str:
        """获取用户视频目录 (deprecated, 使用 get_output_i2v_dir)"""
        return self.get_output_i2v_dir()

    def get_user_image_dir(self) -> str:
        """获取用户图片目录 (deprecated, 使用 get_upload_i2v_dir)"""
        return self.get_upload_i2v_dir()

    def init_user_cache(self) -> Dict:
        """初始化用户缓存"""
        cache_file = self.get_user_cache_file()

        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 创建新的用户缓存
        user_cache = {
            'api_key_hash': self.api_key_hash,
            'created_at': datetime.now().isoformat(),
            'tasks': []
        }

        self.save_user_cache(user_cache)
        return user_cache

    def load_user_cache(self) -> Dict:
        """加载用户缓存（已废弃，使用独立文件存储）"""
        # 为了向后兼容，返回空结构
        return {
            'api_key_hash': self.api_key_hash,
            'created_at': datetime.now().isoformat(),
            'tasks': self.get_all_tasks()
        }

    def save_user_cache(self, cache_data: Dict):
        """保存用户缓存（已废弃，使用独立文件存储）"""
        # 为了向后兼容，保留方法但不执行
        pass

    def add_task(self, task_data: Dict):
        """添加图生视频(I2V)任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 'i2v'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 任务ID为空，无法保存")
            return
        
        # 创建任务目录
        tasks_dir = os.path.join(Config.TASK_I2V_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        # 保存为独立的JSON文件
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] I2V任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存I2V任务文件失败: {e}")

    def update_task(self, task_id: str, update_data: Dict):
        """更新图生视频(I2V)任务状态"""
        tasks_dir = os.path.join(Config.TASK_I2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 任务文件不存在: {task_file}")
            return
        
        try:
            # 读取现有任务数据
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            # 更新数据
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            # 写回文件
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] I2V任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新I2V任务失败: {e}")

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取图生视频(I2V)任务信息"""
        tasks_dir = os.path.join(Config.TASK_I2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取I2V任务文件失败: {e}")
            return None

    def get_all_tasks(self) -> List[Dict]:
        """获取所有图生视频(I2V)任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_I2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            # 遍历所有任务文件
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取任务文件失败 {filename}: {e}")
            
            # 按创建时间降序排序
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取I2V任务列表失败: {e}")
            return []
    
    def get_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取图生视频(I2V)任务 - 高性能版本（批次完整性保证）
        
        确保同一批次的任务不会被分割到不同页面，解决侧边导航显示不一致问题。
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_I2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            # 第一步：加载所有任务的基本信息
            all_tasks = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            # 验证任务数据完整性
                            if not task_data.get('task_id'):
                                print(f"[WARN] 跳过无效I2V任务文件(无task_id): {filename}")
                                continue
                            mtime = os.path.getmtime(task_file)
                            task_data['_mtime'] = mtime
                            all_tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取I2V任务文件失败: {filename}, {e}")
            
            if not all_tasks:
                return [], 0, False
            
            # 第二步：按批次分组
            batch_groups = {}  # batch_id -> [tasks]
            standalone_tasks = []  # 没有batch_id的独立任务
            
            for task in all_tasks:
                batch_id = task.get('batch_id')
                if batch_id:
                    if batch_id not in batch_groups:
                        batch_groups[batch_id] = []
                    batch_groups[batch_id].append(task)
                else:
                    standalone_tasks.append(task)
            
            # 第三步：对每个批次内的任务按batch_index排序，并验证/修复数据一致性
            for batch_id, tasks in batch_groups.items():
                tasks.sort(key=lambda x: x.get('batch_index', 0))
                
                # 验证并修复批次数据一致性
                actual_count = len(tasks)
                for i, task in enumerate(tasks):
                    expected_total = task.get('batch_total', 1)
                    
                    # 如果实际数量与记录的总数不匹配，更新为实际数量
                    if expected_total != actual_count:
                        task['batch_total'] = actual_count
                    
                    # 确保batch_index连续
                    task['batch_index'] = i + 1
            
            # 第四步：将批次按最新任务时间排序，形成有序的批次列表
            batch_list = []
            for batch_id, tasks in batch_groups.items():
                max_mtime = max(t.get('_mtime', 0) for t in tasks)
                batch_list.append((batch_id, tasks, max_mtime))
            
            # 独立任务也作为单独的"批次"
            for task in standalone_tasks:
                batch_list.append((task['task_id'], [task], task.get('_mtime', 0)))
            
            # 按时间倒序排列
            batch_list.sort(key=lambda x: x[2], reverse=True)
            
            # 第五步：分页（按批次分页，确保批次完整性）
            total_batches = len(batch_list)
            start = (page - 1) * limit
            end = start + limit
            
            # 取出当前页的批次
            page_batches = batch_list[start:end]
            has_more = end < total_batches
            
            # 展开批次为任务列表
            tasks = []
            for _, batch_tasks, _ in page_batches:
                tasks.extend(batch_tasks)
            
            # 清除临时字段
            for task in tasks:
                task.pop('_mtime', None)
            
            return tasks, total_batches, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取I2V任务失败: {e}")
            return [], 0, False

    def save_image(self, task_id: str, image_data: bytes, ext: str = 'png') -> str:
        """保存图片到本地 (deprecated)"""
        image_dir = self.get_upload_i2v_dir()
        image_path = os.path.join(image_dir, f'{task_id}.{ext}')

        try:
            with open(image_path, 'wb') as f:
                f.write(image_data)
            return image_path
        except Exception as e:
            print(f"保存图片失败: {e}")
            return None

    def download_video(self, task_id: str, video_url: str, max_retries: int = 3) -> Optional[str]:
        """下载图生视频(I2V)视频到本地
        
        Args:
            task_id: 任务ID
            video_url: 视频URL
            max_retries: 最大重试次数
            
        Returns:
            视频文件路径或None
        """
        video_dir = self.get_output_i2v_dir()
        video_path = os.path.join(video_dir, f'{task_id}.mp4')

        # 如果已经下载过，直接返回路径
        if os.path.exists(video_path):
            print(f"视频已存在: {video_path}")
            return video_path

        # 重试下载
        for attempt in range(max_retries):
            try:
                print(f"开始下载视频 (第{attempt + 1}/{max_retries}次尝试): {task_id}")
                response = self._session.get(video_url, stream=True, timeout=300)
                response.raise_for_status()

                # 临时文件，下载成功后再重命名
                temp_path = f"{video_path}.tmp"
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # 下载成功，重命名
                os.rename(temp_path, video_path)
                print(f"视频下载成功: {video_path}")
                return video_path
                
            except Exception as e:
                print(f"下载视频失败 (第{attempt + 1}/{max_retries}次): {e}")
                
                # 删除临时文件
                temp_path = f"{video_path}.tmp"
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                # 如果不是最后一次尝试，等待一下再重试
                if attempt < max_retries - 1:
                    import time
                    wait_time = (attempt + 1) * 2  # 递增等待时间: 2秒, 4秒, 6秒...
                    print(f"等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        print(f"I2V视频下载失败，已达最大重试次数: {task_id}")
        return None

    def get_video_path(self, task_id: str) -> Optional[str]:
        """获取图生视频(I2V)本地视频路径"""
        video_dir = self.get_output_i2v_dir()
        video_path = os.path.join(video_dir, f'{task_id}.mp4')

        if os.path.exists(video_path):
            return video_path

        return None

    def get_image_path(self, task_id: str) -> Optional[str]:
        """获取本地图片路径 (deprecated)"""
        image_dir = self.get_upload_i2v_dir()

        # 尝试不同的扩展名
        for ext in ['png', 'jpg', 'jpeg', 'webp', 'bmp']:
            image_path = os.path.join(image_dir, f'{task_id}.{ext}')
            if os.path.exists(image_path):
                return image_path

        return None

    def cleanup_expired_cache(self, days: int = 30):
        """清理过期缓存（可选功能）"""
        # TODO: 实现清理逻辑
        pass
    
    # ========== 首尾帧生视频任务管理 ==========
    
    def add_kf2v_task(self, task_data: Dict):
        """添加首尾帧任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 'kf2v'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 首尾帧任务ID为空，无法保存")
            return
        
        # 创建任务目录
        tasks_dir = os.path.join(Config.TASK_KF2V_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        # 保存为独立的JSON文件
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 首尾帧任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存首尾帧任务文件失败: {e}")
    
    def update_kf2v_task(self, task_id: str, update_data: Dict):
        """更新首尾帧任务状态"""
        tasks_dir = os.path.join(Config.TASK_KF2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 首尾帧任务文件不存在: {task_file}")
            return
        
        try:
            # 读取现有任务数据
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            # 更新数据
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            # 写回文件
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] 首尾帧任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新首尾帧任务失败: {e}")
    
    def get_kf2v_task(self, task_id: str) -> Optional[Dict]:
        """获取单个首尾帧任务信息"""
        tasks_dir = os.path.join(Config.TASK_KF2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取首尾帧任务文件失败: {e}")
            return None
    
    def get_all_kf2v_tasks(self) -> List[Dict]:
        """获取所有首尾帧任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_KF2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            # 遍历所有任务文件
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取首尾帧任务文件失败 {filename}: {e}")
            
            # 按创建时间降序排序
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取首尾帧任务列表失败: {e}")
            return []
    
    def get_kf2v_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取首尾帧任务 - 高性能版本
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_KF2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        file_list.append((task_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            tasks = []
            for task_file, _ in page_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"[WARN] 读取任务文件失败: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return tasks, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取首尾帧任务失败: {e}")
            return [], 0, False
    
    # ========== 参考生视频任务管理 ==========
    
    def add_r2v_task(self, task_data: Dict):
        """添加参考生视频任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 'r2v'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 参考生视频任务ID为空，无法保存")
            return
        
        # 创建任务目录
        tasks_dir = os.path.join(Config.TASK_R2V_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        # 保存为独立的JSON文件
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 参考生视频任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存参考生视频任务文件失败: {e}")
    
    def update_r2v_task(self, task_id: str, update_data: Dict):
        """更新参考生视频任务状态"""
        tasks_dir = os.path.join(Config.TASK_R2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 参考生视频任务文件不存在: {task_file}")
            return
        
        try:
            # 读取现有任务数据
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            # 更新数据
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            # 写回文件
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] 参考生视频任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新参考生视频任务失败: {e}")
    
    def get_r2v_task(self, task_id: str) -> Optional[Dict]:
        """获取单个参考生视频任务信息"""
        tasks_dir = os.path.join(Config.TASK_R2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取参考生视频任务文件失败: {e}")
            return None
    
    def get_all_r2v_tasks(self) -> List[Dict]:
        """获取所有参考生视频任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_R2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            # 遍历所有任务文件
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取参考生视频任务文件失败 {filename}: {e}")
            
            # 按创建时间降序排序
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取参考生视频任务列表失败: {e}")
            return []
    
    def get_r2v_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取参考生视频任务 - 高性能版本
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_R2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        file_list.append((task_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            tasks = []
            for task_file, _ in page_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"[WARN] 读取任务文件失败: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return tasks, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取参考生视频任务失败: {e}")
            return [], 0, False
    
    # ========== 文生图任务管理 ==========
    
    def add_t2i_task(self, task_data: Dict):
        """添加文生图任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 't2i'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 文生图任务ID为空，无法保存")
            return
        
        tasks_dir = os.path.join(Config.TASK_T2I_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 文生图任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存文生图任务文件失败: {e}")
    
    def update_t2i_task(self, task_id: str, update_data: Dict):
        """更新文生图任务状态"""
        tasks_dir = os.path.join(Config.TASK_T2I_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 文生图任务文件不存在: {task_file}")
            return
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] 文生图任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新文生图任务失败: {e}")
    
    def get_t2i_task(self, task_id: str) -> Optional[Dict]:
        """获取单个文生图任务信息"""
        tasks_dir = os.path.join(Config.TASK_T2I_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取文生图任务文件失败: {e}")
            return None
    
    def get_all_t2i_tasks(self) -> List[Dict]:
        """获取所有文生图任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_T2I_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取文生图任务文件失败 {filename}: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取文生图任务列表失败: {e}")
            return []
    
    def get_t2i_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取文生图任务 - 高性能版本
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_T2I_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        file_list.append((task_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            tasks = []
            for task_file, _ in page_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"[WARN] 读取任务文件失败: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return tasks, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取文生图任务失败: {e}")
            return [], 0, False
    
    def download_t2i_images(self, task_id: str, image_urls: List[str], max_retries: int = 3) -> List[str]:
        """下载文生图生成的图片到本地
        
        Args:
            task_id: 任务ID
            image_urls: 图片URL列表
            max_retries: 最大重试次数
            
        Returns:
            本地图片文件名列表
        """
        # 文生图输出目录
        output_dir = self.get_output_t2i_dir()
        
        local_filenames = []
        
        for idx, image_url in enumerate(image_urls):
            # 生成本地文件名
            filename = f"{task_id}_{idx}.jpg"
            image_path = os.path.join(output_dir, filename)
            
            # 如果已经下载过，直接添加到列表
            if os.path.exists(image_path):
                print(f"[INFO] 文生图图片已存在: {image_path}")
                local_filenames.append(filename)
                continue
            
            # 重试下载
            for attempt in range(max_retries):
                try:
                    print(f"[INFO] 开始下载文生图图片 (第{attempt + 1}/{max_retries}次尝试): {task_id}_{idx}")
                    response = self._session.get(image_url, stream=True, timeout=60)
                    
                    # 如果是404错误,等待后重试
                    if response.status_code == 404:
                        if attempt < max_retries - 1:
                            wait_time = 2
                            print(f"[WARN] 图片URL返回404,等待{wait_time}秒后重试...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"[ERROR] 图片URL持续404,下载失败: {task_id}_{idx}")
                            break
                    
                    response.raise_for_status()
                    
                    # 临时文件
                    temp_path = f"{image_path}.tmp"
                    
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # 下载成功，重命名
                    os.rename(temp_path, image_path)
                    print(f"[INFO] 文生图图片下载成功: {image_path}")
                    local_filenames.append(filename)
                    break
                    
                except Exception as e:
                    print(f"[ERROR] 下载文生图图片失败 (第{attempt + 1}/{max_retries}次): {e}")
                    
                    # 删除临时文件
                    temp_path = f"{image_path}.tmp"
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"[INFO] 等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
        
        return local_filenames
    
    # ========== 图生图任务管理 ==========
    
    def add_i2i_task(self, task_data: Dict):
        """添加图生图任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 'i2i'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 图生图任务ID为空，无法保存")
            return
        
        tasks_dir = os.path.join(Config.TASK_I2I_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 图生图任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存图生图任务文件失败: {e}")
    
    def update_i2i_task(self, task_id: str, update_data: Dict):
        """更新图生图任务状态"""
        tasks_dir = os.path.join(Config.TASK_I2I_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 图生图任务文件不存在: {task_file}")
            return
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] 图生图任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新图生图任务失败: {e}")
    
    def get_i2i_task(self, task_id: str) -> Optional[Dict]:
        """获取单个图生图任务信息"""
        tasks_dir = os.path.join(Config.TASK_I2I_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取图生图任务文件失败: {e}")
            return None
    
    def get_all_i2i_tasks(self) -> List[Dict]:
        """获取所有图生图任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_I2I_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取图生图任务文件失败 {filename}: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取图生图任务列表失败: {e}")
            return []
    
    def get_i2i_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取图生图任务 - 高性能版本（批次完整性保证）
        
        确保同一批次的任务不会被分割到不同页面，解决侧边导航显示不一致问题。
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_I2I_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            # 第一步：加载所有任务的基本信息
            all_tasks = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            # 验证任务数据完整性
                            if not task_data.get('task_id'):
                                print(f"[WARN] 跳过无效任务文件(无task_id): {filename}")
                                continue
                            mtime = os.path.getmtime(task_file)
                            task_data['_mtime'] = mtime
                            all_tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取任务文件失败: {filename}, {e}")
            
            if not all_tasks:
                return [], 0, False
            
            # 第二步：按批次分组
            batch_groups = {}  # batch_id -> [tasks]
            standalone_tasks = []  # 没有batch_id的独立任务
            
            for task in all_tasks:
                batch_id = task.get('batch_id')
                if batch_id:
                    if batch_id not in batch_groups:
                        batch_groups[batch_id] = []
                    batch_groups[batch_id].append(task)
                else:
                    standalone_tasks.append(task)
            
            # 第三步：对每个批次内的任务按batch_index排序，并验证/修复数据一致性
            for batch_id, tasks in batch_groups.items():
                tasks.sort(key=lambda x: x.get('batch_index', 0))
                
                # 验证并修复批次数据一致性
                actual_count = len(tasks)
                for i, task in enumerate(tasks):
                    expected_total = task.get('batch_total', 1)
                    
                    # 如果实际数量与记录的总数不匹配，更新为实际数量
                    if expected_total != actual_count:
                        task['batch_total'] = actual_count
                        task['_batch_inconsistent'] = True  # 标记数据不一致
                    
                    # 确保batch_index连续
                    task['batch_index'] = i + 1
            
            # 第四步：将批次按最新任务时间排序，形成有序的批次列表
            batch_list = []
            for batch_id, tasks in batch_groups.items():
                max_mtime = max(t.get('_mtime', 0) for t in tasks)
                batch_list.append((batch_id, tasks, max_mtime))
            
            # 独立任务也作为单独的"批次"
            for task in standalone_tasks:
                batch_list.append((task['task_id'], [task], task.get('_mtime', 0)))
            
            # 按时间倒序排列
            batch_list.sort(key=lambda x: x[2], reverse=True)
            
            # 第五步：分页（按批次分页，确保批次完整性）
            total_batches = len(batch_list)
            start = (page - 1) * limit
            end = start + limit
            
            # 取出当前页的批次
            page_batches = batch_list[start:end]
            has_more = end < total_batches
            
            # 展开批次为任务列表
            tasks = []
            for _, batch_tasks, _ in page_batches:
                tasks.extend(batch_tasks)
            
            # 清除临时字段
            for task in tasks:
                task.pop('_mtime', None)
                task.pop('_batch_inconsistent', None)
            
            # 按创建时间排序（在批次内保持batch_index顺序）
            # 不再做全局排序，保持批次分组的完整性
            
            return tasks, total_batches, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取图生图任务失败: {e}")
            return [], 0, False
    
    def download_i2i_images(self, task_id: str, image_urls: List[str], max_retries: int = 3) -> List[str]:
        """下载图生图生成的图片到本地
        
        Args:
            task_id: 任务ID
            image_urls: 图片URL列表
            max_retries: 最大重试次数
            
        Returns:
            本地图片文件名列表
        """
        # 图生图输出目录
        output_dir = self.get_output_i2i_dir()
        
        local_filenames = []
        
        for idx, image_url in enumerate(image_urls):
            # 生成本地文件名
            filename = f"{task_id}_{idx}.jpg"
            image_path = os.path.join(output_dir, filename)
            
            # 如果已经下载过，直接添加到列表
            if os.path.exists(image_path):
                print(f"[INFO] 图生图图片已存在: {image_path}")
                local_filenames.append(filename)
                continue
            
            # 重试下载
            for attempt in range(max_retries):
                try:
                    print(f"[INFO] 开始下载图生图图片 (第{attempt + 1}/{max_retries}次尝试): {task_id}_{idx}")
                    response = self._session.get(image_url, stream=True, timeout=60)
                    
                    # 如果是404错误,等待后重试
                    if response.status_code == 404:
                        if attempt < max_retries - 1:
                            wait_time = 2
                            print(f"[WARN] 图片URL返回404,等待{wait_time}秒后重试...")
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"[ERROR] 图片URL持续404,下载失败: {task_id}_{idx}")
                            break
                    
                    response.raise_for_status()
                    
                    # 临时文件
                    temp_path = f"{image_path}.tmp"
                    
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # 下载成功，重命名
                    os.rename(temp_path, image_path)
                    print(f"[INFO] 图生图图片下载成功: {image_path}")
                    local_filenames.append(filename)
                    break
                    
                except Exception as e:
                    print(f"[ERROR] 下载图生图图片失败 (第{attempt + 1}/{max_retries}次): {e}")
                    
                    # 删除临时文件
                    temp_path = f"{image_path}.tmp"
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"[INFO] 等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
        
        return local_filenames
    
    # ========== 视频封面图管理 ==========
    
    def get_video_poster_path(self, task_id: str, task_type: str = 'i2v') -> str:
        """获取视频封面图路径
        
        Args:
            task_id: 任务ID
            task_type: 任务类型 ('i2v', 'kf2v', 'r2v', 't2v')
        """
        if task_type == 'kf2v':
            output_dir = os.path.join(Config.OUTPUT_KF2V_DIR, self.api_key_hash)
        elif task_type == 'r2v':
            output_dir = os.path.join(Config.OUTPUT_R2V_DIR, self.api_key_hash)
        elif task_type == 't2v':
            output_dir = os.path.join(Config.OUTPUT_T2V_DIR, self.api_key_hash)
        else:
            output_dir = os.path.join(Config.OUTPUT_I2V_DIR, self.api_key_hash)
        
        poster_dir = os.path.join(output_dir, 'posters')
        os.makedirs(poster_dir, exist_ok=True)
        return os.path.join(poster_dir, f'{task_id}.jpg')
    
    def find_video_path(self, task_id: str) -> tuple:
        """查找视频路径（自动识别任务类型）
        
        Returns:
            (video_path, task_type) 或 (None, None)
        """
        # 先尝试 I2V
        i2v_path = os.path.join(Config.OUTPUT_I2V_DIR, self.api_key_hash, f'{task_id}.mp4')
        if os.path.exists(i2v_path):
            return i2v_path, 'i2v'
        
        # 再尝试 KF2V
        kf2v_path = os.path.join(Config.OUTPUT_KF2V_DIR, self.api_key_hash, f'{task_id}.mp4')
        if os.path.exists(kf2v_path):
            return kf2v_path, 'kf2v'
        
        # 尝试 R2V
        r2v_path = os.path.join(Config.OUTPUT_R2V_DIR, self.api_key_hash, f'{task_id}.mp4')
        if os.path.exists(r2v_path):
            return r2v_path, 'r2v'
        
        # 尝试 T2V
        t2v_path = os.path.join(Config.OUTPUT_T2V_DIR, self.api_key_hash, f'{task_id}.mp4')
        if os.path.exists(t2v_path):
            return t2v_path, 't2v'
        
        return None, None
    
    def generate_video_poster(self, task_id: str, video_path: str = None, task_type: str = None) -> Optional[str]:
        """从视频生成封面图（提取第0.5秒的帧）
        
        Args:
            task_id: 任务ID
            video_path: 视频文件路径，如果为None则自动查找
            task_type: 任务类型，如果为None则自动识别
            
        Returns:
            封面图路径或None
        """
        # 获取视频路径和任务类型
        if video_path is None or task_type is None:
            found_path, found_type = self.find_video_path(task_id)
            if video_path is None:
                video_path = found_path
            if task_type is None:
                task_type = found_type or 'i2v'
        
        poster_path = self.get_video_poster_path(task_id, task_type)
        
        # 如果封面图已存在，直接返回
        if os.path.exists(poster_path):
            return poster_path
        
        if not video_path or not os.path.exists(video_path):
            print(f"[WARN] 视频文件不存在，无法生成封面: {task_id}")
            return None
        
        try:
            # 使用 ffmpeg 提取第0.5秒的帧作为封面
            # -ss 0.5: 跳到0.5秒位置
            # -vframes 1: 只提取1帧
            # -q:v 2: 高质量JPEG (1-31, 越小越好)
            # -vf scale=-1:360: 缩放高度为360px，宽度自适应（减小文件体积）
            cmd = [
                'ffmpeg',
                '-ss', '0.5',
                '-i', video_path,
                '-vframes', '1',
                '-vf', 'scale=-1:360',
                '-q:v', '3',
                '-y',  # 覆盖已存在的文件
                poster_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30  # 30秒超时
            )
            
            if result.returncode == 0 and os.path.exists(poster_path):
                print(f"[INFO] 视频封面生成成功: {poster_path}")
                return poster_path
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                print(f"[ERROR] ffmpeg生成封面失败: {error_msg[:200]}")
                return None
                
        except subprocess.TimeoutExpired:
            print(f"[ERROR] 生成封面超时: {task_id}")
            return None
        except FileNotFoundError:
            print("[ERROR] ffmpeg未安装，请先安装ffmpeg")
            return None
        except Exception as e:
            print(f"[ERROR] 生成封面异常: {e}")
            return None
    
    def get_or_generate_poster(self, task_id: str, video_path: str = None, task_type: str = None) -> Optional[str]:
        """获取封面图，如果不存在则生成
        
        Args:
            task_id: 任务ID
            video_path: 视频文件路径
            task_type: 任务类型，如果为None则自动识别
            
        Returns:
            封面图路径或None
        """
        # 自动识别任务类型
        if video_path is None or task_type is None:
            found_path, found_type = self.find_video_path(task_id)
            if video_path is None:
                video_path = found_path
            if task_type is None:
                task_type = found_type or 'i2v'
        
        poster_path = self.get_video_poster_path(task_id, task_type)
        
        if os.path.exists(poster_path):
            return poster_path
        
        return self.generate_video_poster(task_id, video_path, task_type)

    def download_kf2v_video(self, task_id: str, video_url: str, max_retries: int = 3) -> Optional[str]:
        """下载首尾帧生成的视频到本地,支持404重试
        
        Args:
            task_id: 任务ID
            video_url: 视频URL
            max_retries: 最大重试次数
            
        Returns:
            视频文件路径或None
        """
        video_dir = self.get_output_kf2v_dir()
        video_path = os.path.join(video_dir, f'{task_id}.mp4')

        # 如果已经下载过，直接返回路径
        if os.path.exists(video_path):
            print(f"[INFO] 首尾帧视频已存在: {video_path}")
            return video_path

        # 重试下载,支持404重试
        for attempt in range(max_retries):
            try:
                print(f"[INFO] 开始下载首尾帧视频 (第{attempt + 1}/{max_retries}次尝试): {task_id}")
                response = self._session.get(video_url, stream=True, timeout=300)
                
                # 如果是404错误,等待后重试(URL可能还未生效)
                if response.status_code == 404:
                    if attempt < max_retries - 1:
                        wait_time = 2  # 404重试等待2秒
                        print(f"[WARN] 视频URL返回404,等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[ERROR] 视频URL持续404,下载失败: {task_id}")
                        return None
                
                response.raise_for_status()

                # 临时文件，下载成功后再重命名
                temp_path = f"{video_path}.tmp"
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # 下载成功，重命名
                os.rename(temp_path, video_path)
                print(f"[INFO] 首尾帧视频下载成功: {video_path}")
                return video_path
                
            except Exception as e:
                print(f"[ERROR] 下载首尾帧视频失败 (第{attempt + 1}/{max_retries}次): {e}")
                
                # 删除临时文件
                temp_path = f"{video_path}.tmp"
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                # 如果不是最后一次尝试，等待一下再重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间: 2秒, 4秒, 6秒
                    print(f"[INFO] 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        print(f"[ERROR] 首尾帧视频下载失败，已达最大重试次数: {task_id}")
        return None
    
    def download_r2v_video(self, task_id: str, video_url: str, max_retries: int = 3) -> Optional[str]:
        """下载参考生视频生成的视频到本地,支持404重试
        
        Args:
            task_id: 任务ID
            video_url: 视频URL
            max_retries: 最大重试次数
            
        Returns:
            视频文件路径或None
        """
        video_dir = self.get_output_r2v_dir()
        video_path = os.path.join(video_dir, f'{task_id}.mp4')

        # 如果已经下载过，直接返回路径
        if os.path.exists(video_path):
            print(f"[INFO] 参考生视频已存在: {video_path}")
            return video_path

        # 重试下载,支持404重试
        for attempt in range(max_retries):
            try:
                print(f"[INFO] 开始下载参考生视频 (第{attempt + 1}/{max_retries}次尝试): {task_id}")
                response = self._session.get(video_url, stream=True, timeout=300)
                
                # 如果是404错误,等待后重试(URL可能还未生效)
                if response.status_code == 404:
                    if attempt < max_retries - 1:
                        wait_time = 2  # 404重试等待2秒
                        print(f"[WARN] 视频URL返回404,等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[ERROR] 视频URL持续404,下载失败: {task_id}")
                        return None
                
                response.raise_for_status()

                # 临时文件，下载成功后再重命名
                temp_path = f"{video_path}.tmp"
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # 下载成功，重命名
                os.rename(temp_path, video_path)
                print(f"[INFO] 参考生视频下载成功: {video_path}")
                return video_path
                
            except Exception as e:
                print(f"[ERROR] 下载参考生视频失败 (第{attempt + 1}/{max_retries}次): {e}")
                
                # 删除临时文件
                temp_path = f"{video_path}.tmp"
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                # 如果不是最后一次尝试，等待一下再重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间: 2秒, 4秒, 6秒
                    print(f"[INFO] 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        print(f"[ERROR] 参考生视频下载失败，已达最大重试次数: {task_id}")
        return None

    # ========== 文生视频(T2V)任务管理 ==========
    
    def add_t2v_task(self, task_data: Dict):
        """添加文生视频(T2V)任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 't2v'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 任务ID为空，无法保存")
            return
        
        # 创建任务目录
        tasks_dir = os.path.join(Config.TASK_T2V_DIR, self.api_key_hash)
        os.makedirs(tasks_dir, exist_ok=True)
        
        # 保存为独立的JSON文件
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 文生视频任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存文生视频任务文件失败: {e}")
    
    def update_t2v_task(self, task_id: str, update_data: Dict):
        """更新文生视频(T2V)任务状态"""
        tasks_dir = os.path.join(Config.TASK_T2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            print(f"[WARN] 文生视频任务文件不存在: {task_file}")
            return
        
        try:
            # 读取现有任务数据
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            # 更新数据
            task_data.update(update_data)
            task_data['updated_at'] = datetime.now().isoformat()
            
            # 写回文件
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
                
            print(f"[INFO] 文生视频任务已更新: {task_id}")
        except Exception as e:
            print(f"[ERROR] 更新文生视频任务失败: {e}")
    
    def get_t2v_task(self, task_id: str) -> Optional[Dict]:
        """获取单个文生视频(T2V)任务信息"""
        tasks_dir = os.path.join(Config.TASK_T2V_DIR, self.api_key_hash)
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        
        if not os.path.exists(task_file):
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取文生视频任务文件失败: {e}")
            return None
    
    def get_all_t2v_tasks(self) -> List[Dict]:
        """获取所有文生视频(T2V)任务 - 完整加载版本（慢）"""
        tasks_dir = os.path.join(Config.TASK_T2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return []
        
        tasks = []
        try:
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            tasks.append(task_data)
                    except Exception as e:
                        print(f"[WARN] 读取文生视频任务文件失败 {filename}: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return tasks
            
        except Exception as e:
            print(f"[ERROR] 获取文生视频任务列表失败: {e}")
            return []
    
    def get_t2v_tasks_paginated(self, page: int = 1, limit: int = 10) -> tuple:
        """分页获取文生视频(T2V)任务 - 高性能版本
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_T2V_DIR, self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        file_list.append((task_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            tasks = []
            for task_file, _ in page_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"[WARN] 读取任务文件失败: {e}")
            
            tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return tasks, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取文生视频任务失败: {e}")
            return [], 0, False
    
    def download_t2v_video(self, task_id: str, video_url: str, max_retries: int = 3) -> Optional[str]:
        """下载文生视频生成的视频到本地,支持404重试
        
        Args:
            task_id: 任务ID
            video_url: 视频URL
            max_retries: 最大重试次数
            
        Returns:
            视频文件路径或None
        """
        video_dir = self.get_output_t2v_dir()
        video_path = os.path.join(video_dir, f'{task_id}.mp4')

        # 如果已经下载过，直接返回路径
        if os.path.exists(video_path):
            print(f"[INFO] 文生视频已存在: {video_path}")
            return video_path

        # 重试下载,支持404重试
        for attempt in range(max_retries):
            try:
                print(f"[INFO] 开始下载文生视频 (第{attempt + 1}/{max_retries}次尝试): {task_id}")
                response = self._session.get(video_url, stream=True, timeout=300)
                
                # 如果是404错误,等待后重试(URL可能还未生效)
                if response.status_code == 404:
                    if attempt < max_retries - 1:
                        wait_time = 2  # 404重试等待2秒
                        print(f"[WARN] 视频URL返回404,等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[ERROR] 视频URL持续404,下载失败: {task_id}")
                        return None
                
                response.raise_for_status()

                # 临时文件，下载成功后再重命名
                temp_path = f"{video_path}.tmp"
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # 下载成功，重命名
                os.rename(temp_path, video_path)
                print(f"[INFO] 文生视频下载成功: {video_path}")
                return video_path
                
            except Exception as e:
                print(f"[ERROR] 下载文生视频失败 (第{attempt + 1}/{max_retries}次): {e}")
                
                # 删除临时文件
                temp_path = f"{video_path}.tmp"
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                # 如果不是最后一次尝试，等待一下再重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间: 2秒, 4秒, 6秒
                    print(f"[INFO] 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
        
        print(f"[ERROR] 文生视频下载失败，已达最大重试次数: {task_id}")
        return None

    # ========== 任务索引缓存管理（性能优化）==========
    
    def get_task_index_file(self, task_type: str = 'i2v') -> str:
        """获取任务索引文件路径
        
        Args:
            task_type: 任务类型，i2v/kf2v/r2v/t2v/t2i/i2i
        """
        task_dir_map = {
            'i2v': Config.TASK_I2V_DIR,
            'kf2v': Config.TASK_KF2V_DIR,
            'r2v': Config.TASK_R2V_DIR,
            't2v': Config.TASK_T2V_DIR,
            't2i': Config.TASK_T2I_DIR,
            'i2i': Config.TASK_I2I_DIR
        }
        task_dir = os.path.join(task_dir_map.get(task_type, Config.TASK_I2V_DIR), self.api_key_hash)
        os.makedirs(task_dir, exist_ok=True)
        return os.path.join(task_dir, '_index.json')
    
    def load_task_index(self, task_type: str = 'i2v') -> Dict:
        """加载任务索引
        
        Returns:
            索引字典，包含 total_count, last_updated, task_index, batch_index
        """
        index_file = self.get_task_index_file(task_type)
        
        if not os.path.exists(index_file):
            return {
                'total_count': 0,
                'last_updated': datetime.now().isoformat(),
                'task_index': {},  # task_id -> {page, index_in_page, created_at, batch_id}
                'batch_index': {}  # batch_id -> [task_ids]
            }
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 加载任务索引失败: {e}")
            return {
                'total_count': 0,
                'last_updated': datetime.now().isoformat(),
                'task_index': {},
                'batch_index': {}
            }
    
    def save_task_index(self, index_data: Dict, task_type: str = 'i2v'):
        """保存任务索引"""
        index_file = self.get_task_index_file(task_type)
        
        try:
            index_data['last_updated'] = datetime.now().isoformat()
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 任务索引已保存: {index_file}")
        except Exception as e:
            print(f"[ERROR] 保存任务索引失败: {e}")
    
    def rebuild_task_index(self, task_type: str = 'i2v', limit: int = 10) -> Dict:
        """重建任务索引
        
        扫描所有任务文件，重新构建索引
        
        Args:
            task_type: 任务类型
            limit: 每页数量
        
        Returns:
            新的索引数据
        """
        print(f"[INFO] 开始重建{task_type}任务索引...")
        
        task_dir_map = {
            'i2v': Config.TASK_I2V_DIR,
            'kf2v': Config.TASK_KF2V_DIR,
            'r2v': Config.TASK_R2V_DIR,
            't2v': Config.TASK_T2V_DIR,
            't2i': Config.TASK_T2I_DIR,
            'i2i': Config.TASK_I2I_DIR
        }
        tasks_dir = os.path.join(task_dir_map.get(task_type, Config.TASK_I2V_DIR), self.api_key_hash)
        
        if not os.path.exists(tasks_dir):
            return {
                'total_count': 0,
                'last_updated': datetime.now().isoformat(),
                'task_index': {},
                'batch_index': {}
            }
        
        try:
            # 扫描所有任务文件
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json') and filename != '_index.json':
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        task_id = filename.replace('.json', '')
                        
                        # 快速读取关键信息
                        with open(task_file, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)
                            batch_id = task_data.get('batch_id')
                            created_at = task_data.get('created_at', '')
                        
                        file_list.append({
                            'task_id': task_id,
                            'mtime': mtime,
                            'created_at': created_at,
                            'batch_id': batch_id
                        })
                    except Exception as e:
                        print(f"[WARN] 读取任务文件失败: {filename}, {e}")
            
            # 按时间排序
            file_list.sort(key=lambda x: x['mtime'], reverse=True)
            
            # 构建索引
            task_index = {}
            batch_index = {}
            
            # 按批次分组（用于分页时保持批次完整性）
            batch_groups = {}
            standalone_tasks = []
            
            for task in file_list:
                batch_id = task['batch_id']
                if batch_id:
                    if batch_id not in batch_groups:
                        batch_groups[batch_id] = []
                    batch_groups[batch_id].append(task)
                else:
                    standalone_tasks.append(task)
            
            # 合并批次和独立任务，计算页码
            all_groups = []
            for batch_id, tasks in batch_groups.items():
                all_groups.append({'type': 'batch', 'batch_id': batch_id, 'tasks': tasks})
            for task in standalone_tasks:
                all_groups.append({'type': 'single', 'tasks': [task]})
            
            # 按最新任务时间排序
            all_groups.sort(key=lambda x: max(t['mtime'] for t in x['tasks']), reverse=True)
            
            # 分配页码
            current_page = 1
            page_task_count = 0
            
            for group in all_groups:
                for idx, task in enumerate(group['tasks']):
                    task_id = task['task_id']
                    batch_id = task['batch_id']
                    
                    # 添加到任务索引
                    task_index[task_id] = {
                        'page': current_page,
                        'index_in_page': page_task_count,
                        'created_at': task['created_at'],
                        'batch_id': batch_id
                    }
                    
                    # 添加到批次索引
                    if batch_id:
                        if batch_id not in batch_index:
                            batch_index[batch_id] = []
                        batch_index[batch_id].append(task_id)
                
                # 批次作为整体分页
                page_task_count += len(group['tasks'])
                if page_task_count >= limit:
                    current_page += 1
                    page_task_count = 0
            
            index_data = {
                'total_count': len(file_list),
                'last_updated': datetime.now().isoformat(),
                'task_index': task_index,
                'batch_index': batch_index
            }
            
            # 保存索引
            self.save_task_index(index_data, task_type)
            
            print(f"[INFO] {task_type}任务索引重建完成，共{len(file_list)}个任务")
            return index_data
            
        except Exception as e:
            print(f"[ERROR] 重建任务索引失败: {e}")
            return {
                'total_count': 0,
                'last_updated': datetime.now().isoformat(),
                'task_index': {},
                'batch_index': {}
            }
    
    def locate_task(self, task_id: str, task_type: str = 'i2v') -> Optional[Dict]:
        """定位任务所在页码
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        
        Returns:
            {page, index_in_page, batch_id} 或 None
        """
        index_data = self.load_task_index(task_type)
        
        if not index_data['task_index']:
            # 索引不存在，重建索引
            print(f"[INFO] 任务索引不存在，开始重建...")
            index_data = self.rebuild_task_index(task_type)
        
        return index_data['task_index'].get(task_id)

    # ========== 语音复刻模块 ==========
    
    def get_upload_voice_dir(self) -> str:
        """获取语音样本上传目录"""
        upload_dir = os.path.join(Config.UPLOAD_VOICE_DIR, self.api_key_hash)
        os.makedirs(upload_dir, exist_ok=True)
        return upload_dir
    
    def get_output_voice_dir(self) -> str:
        """获取合成语音输出目录"""
        output_dir = os.path.join(Config.OUTPUT_VOICE_DIR, self.api_key_hash)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir
    
    def add_voice(self, voice_data: Dict):
        """添加音色记录"""
        voice_data['created_at'] = datetime.now().isoformat()
        
        voice_id = voice_data.get('voice_id')
        if not voice_id:
            print("[ERROR] 音色ID为空，无法保存")
            return
        
        voices_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'voices')
        os.makedirs(voices_dir, exist_ok=True)
        
        voice_file = os.path.join(voices_dir, f"{voice_id}.json")
        try:
            with open(voice_file, 'w', encoding='utf-8') as f:
                json.dump(voice_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 音色文件已保存: {voice_file}")
        except Exception as e:
            print(f"[ERROR] 保存音色文件失败: {e}")
    
    def update_voice(self, voice_id: str, update_data: Dict):
        """更新音色状态"""
        voices_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'voices')
        voice_file = os.path.join(voices_dir, f"{voice_id}.json")
        
        if not os.path.exists(voice_file):
            print(f"[WARN] 音色文件不存在: {voice_file}")
            return
        
        try:
            with open(voice_file, 'r', encoding='utf-8') as f:
                voice_data = json.load(f)
            
            voice_data.update(update_data)
            voice_data['updated_at'] = datetime.now().isoformat()
            
            with open(voice_file, 'w', encoding='utf-8') as f:
                json.dump(voice_data, f, ensure_ascii=False, indent=2)
            
            print(f"[INFO] 音色已更新: {voice_id}")
        except Exception as e:
            print(f"[ERROR] 更新音色失败: {e}")
    
    def delete_voice(self, voice_id: str):
        """删除音色记录"""
        voices_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'voices')
        voice_file = os.path.join(voices_dir, f"{voice_id}.json")
        
        if os.path.exists(voice_file):
            try:
                os.remove(voice_file)
                print(f"[INFO] 音色文件已删除: {voice_file}")
            except Exception as e:
                print(f"[ERROR] 删除音色文件失败: {e}")
    
    def get_voice(self, voice_id: str) -> Optional[Dict]:
        """获取单个音色信息"""
        voices_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'voices')
        voice_file = os.path.join(voices_dir, f"{voice_id}.json")
        
        if not os.path.exists(voice_file):
            return None
        
        try:
            with open(voice_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取音色文件失败: {e}")
            return None
    
    def get_voices_paginated(self, page: int = 1, limit: int = 20) -> tuple:
        """分页获取音色列表
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (voices, total, has_more) 元组
        """
        voices_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'voices')
        
        if not os.path.exists(voices_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(voices_dir):
                if filename.endswith('.json'):
                    voice_file = os.path.join(voices_dir, filename)
                    try:
                        mtime = os.path.getmtime(voice_file)
                        file_list.append((voice_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            voices = []
            for voice_file, _ in page_files:
                try:
                    with open(voice_file, 'r', encoding='utf-8') as f:
                        voice_data = json.load(f)
                        voices.append(voice_data)
                except Exception as e:
                    print(f"[WARN] 读取音色文件失败: {e}")
            
            return voices, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取音色列表失败: {e}")
            return [], 0, False
    
    def add_voice_task(self, task_data: Dict):
        """添加语音合成任务记录"""
        task_data['created_at'] = datetime.now().isoformat()
        task_data['task_type'] = 'voice_synth'
        
        task_id = task_data.get('task_id')
        if not task_id:
            print("[ERROR] 语音任务ID为空，无法保存")
            return
        
        tasks_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'tasks')
        os.makedirs(tasks_dir, exist_ok=True)
        
        task_file = os.path.join(tasks_dir, f"{task_id}.json")
        try:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 语音任务文件已保存: {task_file}")
        except Exception as e:
            print(f"[ERROR] 保存语音任务文件失败: {e}")
    
    def get_voice_tasks_paginated(self, page: int = 1, limit: int = 20) -> tuple:
        """分页获取语音合成任务列表
        
        Args:
            page: 页码，从1开始
            limit: 每页数量
            
        Returns:
            (tasks, total, has_more) 元组
        """
        tasks_dir = os.path.join(Config.TASK_VOICE_DIR, self.api_key_hash, 'tasks')
        
        if not os.path.exists(tasks_dir):
            return [], 0, False
        
        try:
            file_list = []
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.json'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        mtime = os.path.getmtime(task_file)
                        file_list.append((task_file, mtime))
                    except OSError:
                        pass
            
            file_list.sort(key=lambda x: x[1], reverse=True)
            
            total = len(file_list)
            start = (page - 1) * limit
            end = start + limit
            page_files = file_list[start:end]
            has_more = end < total
            
            tasks = []
            for task_file, _ in page_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                        tasks.append(task_data)
                except Exception as e:
                    print(f"[WARN] 读取语音任务文件失败: {e}")
            
            return tasks, total, has_more
            
        except Exception as e:
            print(f"[ERROR] 分页获取语音任务失败: {e}")
            return [], 0, False

