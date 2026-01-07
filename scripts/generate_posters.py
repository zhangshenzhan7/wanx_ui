#!/usr/bin/env python3
"""
批量生成视频封面图脚本
为所有已存在的视频生成封面图（缩略图）

用法:
    python scripts/generate_posters.py
    
或指定缓存目录:
    python scripts/generate_posters.py /path/to/cache
"""

import os
import sys
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import Config


def generate_poster(video_path: str, poster_path: str) -> bool:
    """
    从视频生成封面图
    
    Args:
        video_path: 视频文件路径
        poster_path: 封面图输出路径
        
    Returns:
        是否成功
    """
    if os.path.exists(poster_path):
        return True  # 已存在，跳过
    
    try:
        # 使用 ffmpeg 提取第0.5秒的帧
        cmd = [
            'ffmpeg',
            '-ss', '0.5',
            '-i', video_path,
            '-vframes', '1',
            '-vf', 'scale=-1:360',
            '-q:v', '3',
            '-y',
            poster_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30
        )
        
        return result.returncode == 0 and os.path.exists(poster_path)
        
    except Exception as e:
        print(f"  ❌ 生成失败: {e}")
        return False


def process_user_videos(user_video_dir: str) -> tuple:
    """
    处理单个用户的所有视频
    
    Args:
        user_video_dir: 用户视频目录路径
        
    Returns:
        (成功数, 失败数, 跳过数)
    """
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    # 创建 posters 目录
    poster_dir = os.path.join(user_video_dir, 'posters')
    os.makedirs(poster_dir, exist_ok=True)
    
    # 遍历所有 mp4 文件
    for filename in os.listdir(user_video_dir):
        if not filename.endswith('.mp4'):
            continue
        
        video_path = os.path.join(user_video_dir, filename)
        task_id = filename.replace('.mp4', '')
        poster_path = os.path.join(poster_dir, f'{task_id}.jpg')
        
        # 检查是否已存在
        if os.path.exists(poster_path):
            skip_count += 1
            continue
        
        # 生成封面图
        if generate_poster(video_path, poster_path):
            success_count += 1
            print(f"  ✅ {task_id}")
        else:
            fail_count += 1
            print(f"  ❌ {task_id}")
    
    return success_count, fail_count, skip_count


def main():
    print("=" * 50)
    print("🎬 批量生成视频封面图")
    print("=" * 50)
    print()
    
    # 检查 ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        if result.returncode != 0:
            print("❌ ffmpeg 未安装，请先安装 ffmpeg")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ ffmpeg 未安装，请先安装 ffmpeg")
        print("   Ubuntu: sudo apt install ffmpeg")
        print("   macOS: brew install ffmpeg")
        sys.exit(1)
    
    print("✅ ffmpeg 已安装")
    
    # 获取缓存目录
    if len(sys.argv) > 1:
        cache_dir = sys.argv[1]
    else:
        cache_dir = Config.CACHE_DIR
    
    # 新的目录结构: outputs/i2v 和 outputs/kf2v
    outputs_dir = os.path.join(cache_dir, 'outputs')
    
    if not os.path.exists(outputs_dir):
        print(f"❌ 输出目录不存在: {outputs_dir}")
        sys.exit(1)
    
    print(f"📁 输出目录: {outputs_dir}")
    print()
    
    # 统计
    total_success = 0
    total_fail = 0
    total_skip = 0
    
    # 处理 i2v 和 kf2v 两个目录
    for task_type in ['i2v', 'kf2v']:
        type_dir = os.path.join(outputs_dir, task_type)
        if not os.path.exists(type_dir):
            continue
        
        print(f"\n📂 处理 {task_type} 目录...")
        
        # 遍历所有用户目录
        user_dirs = [d for d in os.listdir(type_dir) 
                     if os.path.isdir(os.path.join(type_dir, d)) and d != 'posters']
        
        print(f"🔍 找到 {len(user_dirs)} 个用户目录")
        
        for user_hash in user_dirs:
            user_video_dir = os.path.join(type_dir, user_hash)
            
            # 统计视频数量
            video_count = len([f for f in os.listdir(user_video_dir) if f.endswith('.mp4')])
            if video_count == 0:
                continue
            
            print(f"  📂 处理用户 {user_hash[:8]}... ({video_count} 个视频)")
            
            success, fail, skip = process_user_videos(user_video_dir)
            total_success += success
            total_fail += fail
            total_skip += skip
            
            print(f"     新生成: {success}, 失败: {fail}, 已存在: {skip}")
    
    # 总结
    print()
    print("=" * 50)
    print("📊 生成完成!")
    print(f"   ✅ 新生成: {total_success}")
    print(f"   ⏭️  已存在: {total_skip}")
    print(f"   ❌ 失败: {total_fail}")
    print("=" * 50)


if __name__ == '__main__':
    main()
