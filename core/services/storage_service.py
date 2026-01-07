"""
存储服务
统一文件操作接口,处理OSS挂载目录的特殊性
"""
import os
import time
import json
from typing import Optional, Any, List
from datetime import datetime


class StorageService:
    """
    存储服务类
    处理OSS挂载目录(ossfs)的文件同步延迟和并发问题
    """
    
    def __init__(self, cache_dir: str = './cache'):
        """
        初始化存储服务
        
        Args:
            cache_dir: 缓存目录路径(可能是OSS挂载点)
        """
        self.cache_dir = cache_dir
        self.sync_enabled = os.getenv('STORAGE_SYNC_ENABLED', 'true').lower() == 'true'
        self.sync_delay = float(os.getenv('STORAGE_SYNC_DELAY', '0.05'))  # 50ms
        self.read_retry = int(os.getenv('STORAGE_READ_RETRY', '3'))
        self.lock_timeout = int(os.getenv('STORAGE_LOCK_TIMEOUT', '30'))
        
        # 目录列表缓存
        self._dir_cache = {}
        self._dir_cache_ttl = int(os.getenv('DIR_LIST_CACHE_TTL', '30'))
    
    def write_file(self, file_path: str, content: str, sync: bool = True) -> bool:
        """
        写入文件(支持OSS挂载同步)
        
        Args:
            file_path: 文件路径
            content: 文件内容
            sync: 是否强制同步
            
        Returns:
            是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 写入到临时文件
            temp_path = file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                
                # 强制刷盘
                if sync and self.sync_enabled:
                    os.fsync(f.fileno())
            
            # 原子重命名
            os.replace(temp_path, file_path)
            
            # 同步到FUSE层
            if sync and self.sync_enabled:
                try:
                    if hasattr(os, 'sync'):
                        os.sync()
                except:
                    pass
                
                # 等待OSS同步完成
                time.sleep(self.sync_delay)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 写入文件失败 {file_path}: {e}")
            return False
    
    def read_file(self, file_path: str, retry: bool = True) -> Optional[str]:
        """
        读取文件(支持重试)
        
        Args:
            file_path: 文件路径
            retry: 是否启用重试
            
        Returns:
            文件内容或None
        """
        max_retries = self.read_retry if retry else 1
        
        for attempt in range(max_retries):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                if attempt < max_retries - 1:
                    # 文件可能还未同步,等待后重试
                    time.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    return None
            except Exception as e:
                print(f"[ERROR] 读取文件失败 {file_path}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    return None
        
        return None
    
    def write_json(self, file_path: str, data: Any, sync: bool = True) -> bool:
        """
        写入JSON文件
        
        Args:
            file_path: 文件路径
            data: 数据对象
            sync: 是否强制同步
            
        Returns:
            是否成功
        """
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            return self.write_file(file_path, content, sync)
        except Exception as e:
            print(f"[ERROR] 写入JSON失败 {file_path}: {e}")
            return False
    
    def read_json(self, file_path: str, retry: bool = True) -> Optional[Any]:
        """
        读取JSON文件
        
        Args:
            file_path: 文件路径
            retry: 是否启用重试
            
        Returns:
            解析后的数据或None
        """
        content = self.read_file(file_path, retry)
        if content is None:
            return None
        
        try:
            return json.loads(content)
        except Exception as e:
            print(f"[ERROR] 解析JSON失败 {file_path}: {e}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(file_path)
    
    def delete_file(self, file_path: str) -> bool:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            print(f"[ERROR] 删除文件失败 {file_path}: {e}")
            return False
    
    def list_directory(self, dir_path: str, use_cache: bool = True) -> List[str]:
        """
        列举目录(支持缓存)
        
        Args:
            dir_path: 目录路径
            use_cache: 是否使用缓存
            
        Returns:
            文件列表
        """
        # 检查缓存
        if use_cache and dir_path in self._dir_cache:
            cached_data, timestamp = self._dir_cache[dir_path]
            if time.time() - timestamp < self._dir_cache_ttl:
                return cached_data
        
        # 读取目录
        try:
            if not os.path.exists(dir_path):
                return []
            
            files = os.listdir(dir_path)
            
            # 更新缓存
            if use_cache:
                self._dir_cache[dir_path] = (files, time.time())
            
            return files
            
        except Exception as e:
            print(f"[ERROR] 列举目录失败 {dir_path}: {e}")
            return []
    
    def invalidate_cache(self, dir_path: str):
        """失效目录缓存"""
        if dir_path in self._dir_cache:
            del self._dir_cache[dir_path]
    
    def acquire_lock(self, lock_path: str, timeout: Optional[int] = None) -> bool:
        """
        获取文件锁(基于文件名的乐观锁)
        
        Args:
            lock_path: 锁文件路径
            timeout: 超时时间(秒)
            
        Returns:
            是否成功获取锁
        """
        if timeout is None:
            timeout = self.lock_timeout
        
        start_time = time.time()
        
        while True:
            try:
                # 尝试创建锁文件(原子操作)
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                
                # 写入进程信息
                lock_info = {
                    'pid': os.getpid(),
                    'timestamp': time.time()
                }
                os.write(fd, json.dumps(lock_info).encode())
                os.close(fd)
                
                return True
                
            except FileExistsError:
                # 锁已存在,检查是否过期
                if os.path.exists(lock_path):
                    try:
                        stat = os.stat(lock_path)
                        lock_age = time.time() - stat.st_mtime
                        
                        # 锁过期,强制删除
                        if lock_age > self.lock_timeout:
                            print(f"[WARN] 检测到过期锁,强制删除: {lock_path}")
                            os.remove(lock_path)
                            continue
                    except:
                        pass
                
                # 检查超时
                if time.time() - start_time > timeout:
                    print(f"[ERROR] 获取锁超时: {lock_path}")
                    return False
                
                # 等待后重试
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[ERROR] 获取锁失败 {lock_path}: {e}")
                return False
    
    def release_lock(self, lock_path: str):
        """释放文件锁"""
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception as e:
            print(f"[WARN] 释放锁失败 {lock_path}: {e}")


# 全局存储服务实例
_storage_service = None


def get_storage_service(cache_dir: str = './cache') -> StorageService:
    """获取存储服务单例"""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService(cache_dir)
    return _storage_service

