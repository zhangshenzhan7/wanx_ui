#!/usr/bin/env python3
"""
缓存数据迁移脚本（支持并发）
将旧格式的任务数据迁移到新的分类存储格式

旧格式：
./cache/
├── tasks/{api_key_hash}/*.json        # i2v 任务
├── kf2v_tasks/{api_key_hash}/*.json   # kf2v 任务
├── images/{api_key_hash}/              # i2v 上传图片
└── videos/{api_key_hash}/              # i2v 输出视频

新格式：
./cache/
├── tasks/
│   ├── i2v/{api_key_hash}/*.json       # i2v 任务
│   └── kf2v/{api_key_hash}/*.json      # kf2v 任务
├── uploads/
│   ├── i2v/{api_key_hash}/             # i2v 上传图片
│   └── kf2v/{api_key_hash}/            # kf2v 上传图片
└── outputs/
    ├── i2v/{api_key_hash}/             # i2v 输出视频
    └── kf2v/{api_key_hash}/            # kf2v 输出视频

使用方法:
    python scripts/migrate_cache.py --cache-dir ./cache [--dry-run] [--workers 8]
"""

import os
import sys
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time


# 新格式的任务类型目录
TASK_TYPE_DIRS = {'i2v', 'kf2v', 't2i', 'i2i'}


# 线程安全的统计计数器
class AtomicCounter:
    def __init__(self):
        self.value = 0
        self.lock = Lock()
    
    def increment(self, amount=1):
        with self.lock:
            self.value += amount
            return self.value
    
    def get(self):
        with self.lock:
            return self.value


def is_api_key_hash(dirname: str) -> bool:
    """判断目录名是否是 api_key_hash 格式（16位hex）"""
    if len(dirname) not in [16, 32]:
        return False
    return all(c in '0123456789abcdef' for c in dirname.lower())


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def copy_file_task(src: str, dst: str, dry_run: bool = False) -> tuple:
    """
    复制单个文件（用于并发执行）
    
    Returns:
        (success, skipped, error_msg)
    """
    if dry_run:
        return (True, False, None)
    
    # 检查目标文件是否已存在
    if os.path.exists(dst):
        return (False, True, None)  # 跳过
    
    try:
        ensure_dir(os.path.dirname(dst))
        shutil.copy2(src, dst)
        return (True, False, None)
    except Exception as e:
        return (False, False, str(e))


def find_user_dirs(base_dir: str) -> list:
    """查找目录下的所有 api_key_hash 子目录"""
    user_dirs = []
    
    if not os.path.exists(base_dir):
        return user_dirs
    
    for dirname in os.listdir(base_dir):
        dirpath = os.path.join(base_dir, dirname)
        
        # 跳过新格式的类型目录
        if dirname in TASK_TYPE_DIRS:
            continue
        
        # 检查是否是目录且是 api_key_hash 格式
        if os.path.isdir(dirpath) and is_api_key_hash(dirname):
            user_dirs.append({
                'dirpath': dirpath,
                'api_key_hash': dirname
            })
    
    return user_dirs


def collect_copy_tasks(old_dir: str, new_dir: str, extensions: list = None) -> list:
    """
    收集所有需要复制的文件任务
    
    Args:
        old_dir: 旧目录
        new_dir: 新目录
        extensions: 文件扩展名列表，None表示所有文件
    
    Returns:
        [(src, dst), ...]
    """
    tasks = []
    
    user_dirs = find_user_dirs(old_dir)
    
    for ud in user_dirs:
        api_key_hash = ud['api_key_hash']
        old_user_dir = ud['dirpath']
        new_user_dir = os.path.join(new_dir, api_key_hash)
        
        if not os.path.isdir(old_user_dir):
            continue
        
        for filename in os.listdir(old_user_dir):
            src = os.path.join(old_user_dir, filename)
            
            if not os.path.isfile(src):
                continue
            
            # 检查扩展名
            if extensions:
                if not any(filename.lower().endswith(ext) for ext in extensions):
                    continue
            
            dst = os.path.join(new_user_dir, filename)
            tasks.append((src, dst))
    
    return tasks


def collect_task_copy_tasks(old_tasks_dir: str, new_tasks_base: str, task_type: str) -> list:
    """
    收集任务文件复制任务
    
    Args:
        old_tasks_dir: 旧任务目录 (./cache/tasks 或 ./cache/kf2v_tasks)
        new_tasks_base: 新任务基础目录 (./cache/tasks)
        task_type: 任务类型 ('i2v' 或 'kf2v')
    
    Returns:
        [(src, dst), ...]
    """
    tasks = []
    
    user_dirs = find_user_dirs(old_tasks_dir)
    
    for ud in user_dirs:
        api_key_hash = ud['api_key_hash']
        old_user_dir = ud['dirpath']
        new_user_dir = os.path.join(new_tasks_base, task_type, api_key_hash)
        
        if not os.path.isdir(old_user_dir):
            continue
        
        for filename in os.listdir(old_user_dir):
            if not filename.endswith('.json'):
                continue
            
            src = os.path.join(old_user_dir, filename)
            dst = os.path.join(new_user_dir, filename)
            tasks.append((src, dst))
    
    return tasks


def execute_copy_tasks(tasks: list, workers: int, dry_run: bool = False) -> dict:
    """
    并发执行复制任务
    
    Args:
        tasks: [(src, dst), ...]
        workers: 并发线程数
        dry_run: 预览模式
    
    Returns:
        统计信息
    """
    stats = {
        'total': len(tasks),
        'copied': 0,
        'skipped': 0,
        'errors': 0
    }
    
    if not tasks:
        return stats
    
    copied = AtomicCounter()
    skipped = AtomicCounter()
    errors = AtomicCounter()
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(copy_file_task, src, dst, dry_run): (src, dst)
            for src, dst in tasks
        }
        
        for future in as_completed(futures):
            success, was_skipped, error_msg = future.result()
            if success:
                copied.increment()
            elif was_skipped:
                skipped.increment()
            else:
                errors.increment()
                if error_msg:
                    src, dst = futures[future]
                    print(f"  [ERROR] {os.path.basename(src)}: {error_msg}")
    
    stats['copied'] = copied.get()
    stats['skipped'] = skipped.get()
    stats['errors'] = errors.get()
    
    return stats


def migrate_all(cache_dir: str, workers: int = 8, dry_run: bool = False):
    """执行完整迁移"""
    print("=" * 60)
    print("缓存数据迁移脚本 (并发版)")
    print("=" * 60)
    print(f"缓存目录: {cache_dir}")
    print(f"并发线程: {workers}")
    print(f"模式: {'预览模式 (不执行实际操作)' if dry_run else '执行模式'}")
    print()
    
    start_time = time.time()
    
    total_stats = {
        'i2v_tasks': 0,
        'kf2v_tasks': 0,
        'images': 0,
        'videos': 0,
        'skipped': 0,
        'errors': 0
    }
    
    # ========== 1. 迁移 i2v 任务 ==========
    print("[1/4] 迁移 i2v 任务: ./cache/tasks/{hash}/ -> ./cache/tasks/i2v/{hash}/")
    old_tasks_dir = os.path.join(cache_dir, 'tasks')
    new_tasks_dir = os.path.join(cache_dir, 'tasks')
    
    if os.path.exists(old_tasks_dir):
        tasks = collect_task_copy_tasks(old_tasks_dir, new_tasks_dir, 'i2v')
        print(f"  发现 {len(tasks)} 个文件...")
        
        if tasks:
            stats = execute_copy_tasks(tasks, workers, dry_run)
            total_stats['i2v_tasks'] = stats['copied']
            total_stats['skipped'] += stats['skipped']
            total_stats['errors'] += stats['errors']
            print(f"  复制: {stats['copied']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
    else:
        print("  [跳过] 目录不存在")
    print()
    
    # ========== 2. 迁移 kf2v 任务 ==========
    print("[2/4] 迁移 kf2v 任务: ./cache/kf2v_tasks/{hash}/ -> ./cache/tasks/kf2v/{hash}/")
    old_kf2v_tasks_dir = os.path.join(cache_dir, 'kf2v_tasks')
    
    if os.path.exists(old_kf2v_tasks_dir):
        tasks = collect_task_copy_tasks(old_kf2v_tasks_dir, new_tasks_dir, 'kf2v')
        print(f"  发现 {len(tasks)} 个文件...")
        
        if tasks:
            stats = execute_copy_tasks(tasks, workers, dry_run)
            total_stats['kf2v_tasks'] = stats['copied']
            total_stats['skipped'] += stats['skipped']
            total_stats['errors'] += stats['errors']
            print(f"  复制: {stats['copied']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
    else:
        print("  [跳过] 目录不存在")
    print()
    
    # ========== 3. 迁移 i2v 上传图片 ==========
    print("[3/4] 迁移 i2v 上传图片: ./cache/images/{hash}/ -> ./cache/uploads/i2v/{hash}/")
    old_images_dir = os.path.join(cache_dir, 'images')
    new_images_dir = os.path.join(cache_dir, 'uploads', 'i2v')
    image_exts = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif']
    
    if os.path.exists(old_images_dir):
        tasks = collect_copy_tasks(old_images_dir, new_images_dir, image_exts)
        print(f"  发现 {len(tasks)} 个文件...")
        
        if tasks:
            stats = execute_copy_tasks(tasks, workers, dry_run)
            total_stats['images'] = stats['copied']
            total_stats['skipped'] += stats['skipped']
            total_stats['errors'] += stats['errors']
            print(f"  复制: {stats['copied']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
    else:
        print("  [跳过] 目录不存在")
    print()
    
    # ========== 4. 迁移 i2v 输出视频 ==========
    print("[4/4] 迁移 i2v 输出视频: ./cache/videos/{hash}/ -> ./cache/outputs/i2v/{hash}/")
    old_videos_dir = os.path.join(cache_dir, 'videos')
    new_videos_dir = os.path.join(cache_dir, 'outputs', 'i2v')
    video_exts = ['.mp4', '.webm', '.mov']
    
    if os.path.exists(old_videos_dir):
        tasks = collect_copy_tasks(old_videos_dir, new_videos_dir, video_exts)
        print(f"  发现 {len(tasks)} 个文件...")
        
        if tasks:
            stats = execute_copy_tasks(tasks, workers, dry_run)
            total_stats['videos'] = stats['copied']
            total_stats['skipped'] += stats['skipped']
            total_stats['errors'] += stats['errors']
            print(f"  复制: {stats['copied']}, 跳过: {stats['skipped']}, 错误: {stats['errors']}")
    else:
        print("  [跳过] 目录不存在")
    print()
    
    # ========== 统计汇总 ==========
    elapsed = time.time() - start_time
    
    print("=" * 60)
    print("迁移完成！统计信息：")
    print("=" * 60)
    print(f"i2v 任务: {total_stats['i2v_tasks']}")
    print(f"kf2v 任务: {total_stats['kf2v_tasks']}")
    print(f"i2v 图片: {total_stats['images']}")
    print(f"i2v 视频: {total_stats['videos']}")
    print(f"跳过 (已存在): {total_stats['skipped']}")
    print(f"错误数: {total_stats['errors']}")
    print(f"耗时: {elapsed:.2f} 秒")
    
    if dry_run:
        print()
        print("="* 60)
        print("这是预览模式，没有执行实际操作。")
        print("移除 --dry-run 参数以执行实际迁移。")
        print("="* 60)


def main():
    parser = argparse.ArgumentParser(
        description='将旧格式缓存数据迁移到新格式（支持并发）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
旧格式:
  ./cache/tasks/{api_key_hash}/        -> i2v 任务
  ./cache/kf2v_tasks/{api_key_hash}/   -> kf2v 任务
  ./cache/images/{api_key_hash}/       -> i2v 上传图片
  ./cache/videos/{api_key_hash}/       -> i2v 输出视频

新格式:
  ./cache/tasks/i2v/{api_key_hash}/    -> i2v 任务
  ./cache/tasks/kf2v/{api_key_hash}/   -> kf2v 任务
  ./cache/uploads/i2v/{api_key_hash}/  -> i2v 上传图片
  ./cache/outputs/i2v/{api_key_hash}/  -> i2v 输出视频

示例:
  # 预览模式（不执行实际操作）
  python scripts/migrate_cache.py --cache-dir /nas/cache --dry-run
  
  # 使用 16 个线程执行迁移
  python scripts/migrate_cache.py --cache-dir /nas/cache --workers 16
  
  # 默认 8 个线程执行迁移
  python scripts/migrate_cache.py --cache-dir /nas/cache
        """
    )
    
    parser.add_argument(
        '--cache-dir',
        default='./cache',
        help='缓存目录路径 (默认: ./cache)'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=8,
        help='并发线程数 (默认: 8)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不执行实际操作'
    )
    
    args = parser.parse_args()
    
    # 转换为绝对路径
    cache_dir = os.path.abspath(args.cache_dir)
    
    if not os.path.exists(cache_dir):
        print(f"错误: 缓存目录不存在: {cache_dir}")
        sys.exit(1)
    
    migrate_all(cache_dir, args.workers, args.dry_run)


if __name__ == '__main__':
    main()
