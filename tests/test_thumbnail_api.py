"""测试缩略图API返回数据"""
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from services.cache_service import CacheService


def test_t2i_thumbnails():
    """测试文生图缩略图API数据"""
    print("=" * 60)
    print("=== 测试 T2I 缩略图 API ===")
    print("=" * 60)
    
    task_dir = Config.TASK_T2I_DIR
    print(f"任务目录: {task_dir}")
    
    if not os.path.exists(task_dir):
        print("❌ T2I 任务目录不存在")
        return
    
    users = [d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))]
    print(f"用户数量: {len(users)}")
    
    for user in users[:2]:  # 只测试前2个用户
        user_dir = os.path.join(task_dir, user)
        files = [f for f in os.listdir(user_dir) if f.endswith('.json')]
        print(f"\n用户 {user[:16]}...")
        print(f"  任务文件数: {len(files)}")
        
        if not files:
            continue
        
        # 测试缓存服务
        cs = CacheService(user)
        tasks, total, has_more = cs.get_t2i_tasks_paginated(1, 50)
        print(f"  get_t2i_tasks_paginated 结果:")
        print(f"    返回任务数: {len(tasks)}")
        print(f"    total: {total}")
        print(f"    has_more: {has_more}")
        
        # 统计成功的任务
        succeeded = [t for t in tasks if t.get('task_status') == 'SUCCEEDED']
        print(f"    成功任务数: {len(succeeded)}")
        
        # 检查批次信息
        with_batch = [t for t in tasks if t.get('batch_id')]
        print(f"    有 batch_id 的任务: {len(with_batch)}")
        
        # 检查图片URL
        with_images = [t for t in succeeded if t.get('local_image_urls') or t.get('image_urls')]
        print(f"    有图片URL的成功任务: {len(with_images)}")
        
        if succeeded:
            task = succeeded[0]
            print(f"\n  第一个成功任务详情:")
            print(f"    task_id: {task.get('task_id')}")
            print(f"    task_status: {task.get('task_status')}")
            print(f"    batch_id: {task.get('batch_id')}")
            print(f"    batch_total: {task.get('batch_total')}")
            print(f"    batch_index: {task.get('batch_index')}")
            print(f"    local_image_urls: {task.get('local_image_urls', [])[:2]}")
            print(f"    image_urls: {task.get('image_urls', [])[:2]}")


def test_i2i_thumbnails():
    """测试图生图缩略图API数据"""
    print("\n" + "=" * 60)
    print("=== 测试 I2I 缩略图 API ===")
    print("=" * 60)
    
    task_dir = Config.TASK_I2I_DIR
    print(f"任务目录: {task_dir}")
    
    if not os.path.exists(task_dir):
        print("❌ I2I 任务目录不存在")
        return
    
    users = [d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))]
    print(f"用户数量: {len(users)}")
    
    for user in users[:2]:
        user_dir = os.path.join(task_dir, user)
        files = [f for f in os.listdir(user_dir) if f.endswith('.json')]
        print(f"\n用户 {user[:16]}...")
        print(f"  任务文件数: {len(files)}")
        
        if not files:
            continue
        
        cs = CacheService(user)
        tasks, total, has_more = cs.get_i2i_tasks_paginated(1, 50)
        print(f"  get_i2i_tasks_paginated 结果:")
        print(f"    返回任务数: {len(tasks)}")
        print(f"    total: {total}")
        print(f"    has_more: {has_more}")
        
        succeeded = [t for t in tasks if t.get('task_status') == 'SUCCEEDED']
        print(f"    成功任务数: {len(succeeded)}")
        
        with_batch = [t for t in tasks if t.get('batch_id')]
        print(f"    有 batch_id 的任务: {len(with_batch)}")
        
        with_images = [t for t in succeeded if t.get('local_image_urls') or t.get('image_urls')]
        print(f"    有图片URL的成功任务: {len(with_images)}")
        
        if succeeded:
            task = succeeded[0]
            print(f"\n  第一个成功任务详情:")
            print(f"    task_id: {task.get('task_id')}")
            print(f"    task_status: {task.get('task_status')}")
            print(f"    batch_id: {task.get('batch_id')}")
            print(f"    batch_total: {task.get('batch_total')}")
            print(f"    batch_index: {task.get('batch_index')}")
            print(f"    local_image_urls: {task.get('local_image_urls', [])[:2]}")
            print(f"    image_urls: {task.get('image_urls', [])[:2]}")


def simulate_thumbnail_api(task_type='t2i'):
    """模拟缩略图API的处理逻辑"""
    print("\n" + "=" * 60)
    print(f"=== 模拟 {task_type.upper()} 缩略图 API 处理 ===")
    print("=" * 60)
    
    if task_type == 't2i':
        task_dir = Config.TASK_T2I_DIR
    else:
        task_dir = Config.TASK_I2I_DIR
    
    if not os.path.exists(task_dir):
        print(f"❌ {task_type.upper()} 任务目录不存在")
        return
    
    users = [d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))]
    if not users:
        print("❌ 没有用户数据")
        return
    
    user = users[0]
    print(f"测试用户: {user[:16]}...")
    
    cs = CacheService(user)
    
    if task_type == 't2i':
        tasks, total_batches, has_more = cs.get_t2i_tasks_paginated(1, 50)
    else:
        tasks, total_batches, has_more = cs.get_i2i_tasks_paginated(1, 50)
    
    print(f"\n原始数据: {len(tasks)} 个任务, total={total_batches}, has_more={has_more}")
    
    # 模拟缩略图API的批次分组逻辑
    batch_thumbnails = {}
    standalone_thumbnails = []
    
    for task in tasks:
        if task.get('task_status') != 'SUCCEEDED':
            continue
        
        # 获取缩略图URL
        poster_url = ''
        if task.get('local_image_urls') and len(task['local_image_urls']) > 0:
            poster_url = task['local_image_urls'][0]
        elif task.get('image_urls') and len(task['image_urls']) > 0:
            poster_url = task['image_urls'][0]
        
        if not poster_url:
            print(f"  ⚠️ 任务 {task['task_id'][:16]}... 没有图片URL")
            continue
        
        batch_id = task.get('batch_id')
        batch_total = task.get('batch_total', 1)
        
        if batch_id:
            if batch_id not in batch_thumbnails:
                batch_thumbnails[batch_id] = {
                    'task_id': task['task_id'],
                    'batch_id': batch_id,
                    'batch_total': batch_total,
                    'batch_completed': 1,
                    'poster_url': poster_url,
                    'type': 'image'
                }
            else:
                batch_thumbnails[batch_id]['batch_completed'] += 1
        else:
            standalone_thumbnails.append({
                'task_id': task['task_id'],
                'batch_id': None,
                'batch_total': 1,
                'batch_completed': 1,
                'poster_url': poster_url,
                'type': 'image'
            })
    
    # 合并
    thumbnails = []
    seen_batch_ids = set()
    
    for task in tasks:
        batch_id = task.get('batch_id')
        task_id = task.get('task_id')
        
        if batch_id:
            if batch_id not in seen_batch_ids and batch_id in batch_thumbnails:
                thumbnails.append(batch_thumbnails[batch_id])
                seen_batch_ids.add(batch_id)
        else:
            for st in standalone_thumbnails:
                if st['task_id'] == task_id:
                    thumbnails.append(st)
                    break
    
    print(f"\n处理结果:")
    print(f"  批次缩略图: {len(batch_thumbnails)}")
    print(f"  独立缩略图: {len(standalone_thumbnails)}")
    print(f"  最终缩略图数量: {len(thumbnails)}")
    
    if thumbnails:
        print(f"\n  前3个缩略图:")
        for i, t in enumerate(thumbnails[:3]):
            print(f"    [{i+1}] task_id={t['task_id'][:16]}..., batch_id={t.get('batch_id', 'N/A')[:8] if t.get('batch_id') else 'None'}, batch={t.get('batch_completed', 1)}/{t.get('batch_total', 1)}")
            print(f"        poster_url={t['poster_url'][:50]}...")
    
    # 模拟API返回
    api_response = {
        'success': True,
        'thumbnails': thumbnails,
        'page': 1,
        'limit': 50,
        'total_tasks': total_batches,
        'has_more': has_more
    }
    
    print(f"\n模拟 API 返回:")
    print(f"  success: {api_response['success']}")
    print(f"  thumbnails 数量: {len(api_response['thumbnails'])}")
    print(f"  total_tasks: {api_response['total_tasks']}")
    print(f"  has_more: {api_response['has_more']}")
    
    return api_response


if __name__ == '__main__':
    print("开始测试缩略图 API 数据...\n")
    
    test_t2i_thumbnails()
    test_i2i_thumbnails()
    
    simulate_thumbnail_api('t2i')
    simulate_thumbnail_api('i2i')
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
