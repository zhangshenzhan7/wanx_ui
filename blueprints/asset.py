"""
资产库（Assets）蓝图模块
包含资产上传、列表、删除、标签管理等功能
"""

from flask import Blueprint, render_template, request, jsonify, session, make_response, send_file
import os
import time
import uuid
import json
import subprocess

from config import Config
from core.utils.session_helper import get_api_key_hash, require_auth
from core.utils.response_helper import success_response, error_response
from core.services.file_service import FileService
from core.services.project_service import ProjectService
from core.handlers.media_handler import MediaHandler


# 创建蓝图
asset_bp = Blueprint('asset', __name__)


def generate_asset_video_poster(video_path: str, poster_path: str) -> bool:
    """为资产视频生成封面图
    
    Args:
        video_path: 视频文件路径
        poster_path: 封面图输出路径
        
    Returns:
        是否成功
    """
    if os.path.exists(poster_path):
        return True  # 已存在
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(poster_path), exist_ok=True)
        
        # 使用 ffmpeg 提取第0.5秒的帧作为封面
        cmd = [
            'ffmpeg',
            '-ss', '0.5',
            '-i', video_path,
            '-vframes', '1',
            '-vf', 'scale=-1:360',  # 缩放高度为360px，减小文件体积
            '-q:v', '3',  # 高质量JPEG
            '-y',  # 覆盖已存在的文件
            poster_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(poster_path):
            print(f"[INFO] 资产视频封面生成成功: {poster_path}")
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            print(f"[ERROR] 资产视频封面生成失败: {error_msg[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[ERROR] ffmpeg超时: {video_path}")
        return False
    except Exception as e:
        print(f"[ERROR] 生成资产视频封面异常: {e}")
        return False


@asset_bp.route('/assets')
def assets_page():
    """资产库页面"""
    if 'api_key_hash' not in session:
        return render_template('index.html')
    return render_template('assets.html')


@asset_bp.route('/api/assets/upload', methods=['POST'])
@require_auth
def upload_asset():
    """上传资产（图片或视频）"""
    try:
        api_key_hash = get_api_key_hash()
        
        # 获取所有上传的文件
        files = request.files.getlist('file')
        if not files or len(files) == 0:
            return error_response('没有上传文件')
        
        # 获取分类信息（使用第一个文件的分类信息）
        category = request.form.get('category', 'storyboard')  # storyboard, artwork, video
        
        # 验证分类
        if category not in ['storyboard', 'artwork', 'video']:
            return error_response('无效的资产分类')
        
        # 存储所有成功上传的文件信息
        uploaded_files = []
        
        # 验证文件类型
        image_exts = {'png', 'jpg', 'jpeg', 'bmp', 'webp', 'gif'}
        video_exts = {'mp4', 'mov', 'avi', 'webm'}
        
        for file in files:
            if file.filename == '':
                continue  # 跳过空文件
            
            # 获取文件扩展名
            original_filename = file.filename
            ext = ''
            if '.' in original_filename:
                ext = original_filename.rsplit('.', 1)[1].lower()
            
            # 验证文件类型
            if category in ['storyboard', 'artwork']:
                if ext not in image_exts:
                    return error_response(f'分镜库和原画库仅支持图片格式，不支持文件: {original_filename}')
            elif category == 'video':
                if ext not in video_exts:
                    return error_response(f'视频库仅支持视频格式，不支持文件: {original_filename}')
            
            # 生成新文件名
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            new_filename = f"{timestamp}_{unique_id}.{ext}" if ext else f"{timestamp}_{unique_id}"
            
            # 根据分类选择目录
            category_dirs = {
                'storyboard': Config.ASSETS_STORYBOARD_DIR,
                'artwork': Config.ASSETS_ARTWORK_DIR,
                'video': Config.ASSETS_VIDEO_DIR
            }
            base_dir = category_dirs[category]
            user_dir = os.path.join(base_dir, api_key_hash)
            os.makedirs(user_dir, exist_ok=True)
            
            filepath = os.path.join(user_dir, new_filename)
            file.save(filepath)
            
            # 同步到磁盘
            try:
                os.sync() if hasattr(os, 'sync') else None
            except:
                pass
            
            # 保存元数据
            meta_filename = new_filename + '.meta.json'
            meta_path = os.path.join(user_dir, meta_filename)
            meta_data = {
                'original_filename': original_filename,
                'filename': new_filename,
                'category': category,
                'upload_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'file_type': 'video' if category == 'video' else 'image'
            }
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            # 如果是视频，生成封面图
            poster_url = None
            if category == 'video':
                poster_dir = os.path.join(user_dir, 'posters')
                poster_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
                poster_path = os.path.join(poster_dir, poster_filename)
                if generate_asset_video_poster(filepath, poster_path):
                    poster_url = f'/api/assets/video-poster/{api_key_hash}/{poster_filename}'
            
            # 添加到上传成功的文件列表
            uploaded_files.append({
                'filename': new_filename,
                'original_filename': original_filename,
                'url': f'/api/assets/{category}/{api_key_hash}/{new_filename}',
                'poster_url': poster_url,
                'category': category
            })
        
        # 同步到磁盘
        try:
            os.sync() if hasattr(os, 'sync') else None
        except:
            pass
        
        return jsonify({
            'success': True,
            'files': uploaded_files,
            'message': f'成功上传 {len(uploaded_files)} 个文件'
        })
    
    except Exception as e:
        print(f"[ERROR] 上传资产失败: {e}")
        return error_response(f'上传失败: {str(e)}')


@asset_bp.route('/api/assets/<category>/<api_key_hash>/<filename>')
def get_asset(category, api_key_hash, filename):
    """获取资产文件"""
    try:
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        base_dir = category_dirs.get(category)
        if not base_dir:
            return jsonify({'error': '无效的资产分类'}), 400
        
        filepath = os.path.join(base_dir, api_key_hash, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 检测MIME类型
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        if category == 'video':
            # 视频使用Range请求
            return MediaHandler.serve_video_with_range(filepath, 'video/mp4')
        else:
            # 图片直接返回
            mime_types = {
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png', 'webp': 'image/webp',
                'bmp': 'image/bmp', 'gif': 'image/gif'
            }
            mimetype = mime_types.get(ext, 'image/png')
            response = make_response(send_file(filepath, mimetype=mimetype))
            response.headers['Cache-Control'] = 'private, max-age=604800'
            response.headers['ETag'] = f'"{os.path.getmtime(filepath)}-{os.path.getsize(filepath)}"'
            return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@asset_bp.route('/api/assets/video-poster/<api_key_hash>/<poster_filename>')
def get_asset_video_poster(api_key_hash, poster_filename):
    """获取资产视频封面图"""
    try:
        poster_dir = os.path.join(Config.ASSETS_VIDEO_DIR, api_key_hash, 'posters')
        poster_path = os.path.join(poster_dir, poster_filename)
        
        if not os.path.exists(poster_path):
            # 尝试根据封面文件名找到视频并生成封面
            video_name = poster_filename.rsplit('.', 1)[0]
            video_dir = os.path.join(Config.ASSETS_VIDEO_DIR, api_key_hash)
            
            # 查找对应的视频文件
            video_path = None
            for ext in ['mp4', 'mov', 'avi', 'webm']:
                candidate = os.path.join(video_dir, f'{video_name}.{ext}')
                if os.path.exists(candidate):
                    video_path = candidate
                    break
            
            if video_path:
                generate_asset_video_poster(video_path, poster_path)
        
        if os.path.exists(poster_path):
            response = make_response(send_file(poster_path, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=2592000'  # 缓存30天
            response.headers['ETag'] = f'"{os.path.getmtime(poster_path)}"'
            return response
        else:
            # 封面图生成失败，返回404
            return jsonify({'error': '封面图不存在'}), 404
            
    except Exception as e:
        print(f"[ERROR] 获取资产视频封面失败: {e}")
        return jsonify({'error': str(e)}), 500


@asset_bp.route('/api/assets/list', methods=['GET'])
@require_auth
def list_assets():
    """获取资产列表"""
    try:
        api_key_hash = get_api_key_hash()
        
        category = request.args.get('category', 'all')  # all, storyboard, artwork, video
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)
        
        # 项目/分集筛选参数
        filter_project = request.args.get('project', '').strip()
        filter_episode = request.args.get('episode', '').strip()
        
        assets = []
        
        # 确定要查询的分类
        if category == 'all':
            categories = ['storyboard', 'artwork', 'video']
        elif category == 'images':  # 特殊分类：所有图片（分镜+原画）
            categories = ['storyboard', 'artwork']
        else:
            categories = [category]
        
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        for cat in categories:
            base_dir = category_dirs.get(cat)
            if not base_dir:
                continue
            
            user_dir = os.path.join(base_dir, api_key_hash)
            if not os.path.exists(user_dir):
                continue
            
            for filename in os.listdir(user_dir):
                if filename.endswith('.meta.json'):
                    continue
                
                # 跳过 posters 目录
                if filename == 'posters':
                    continue
                
                # 读取元数据
                meta_path = os.path.join(user_dir, filename + '.meta.json')
                meta = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                    except:
                        pass
                
                # 根据项目/分集筛选
                asset_project = meta.get('project', '')
                asset_episode = meta.get('episode', '')
                
                if filter_project and asset_project != filter_project:
                    continue
                if filter_episode and asset_episode != filter_episode:
                    continue
                
                filepath = os.path.join(user_dir, filename)
                file_type = meta.get('file_type', 'image' if cat != 'video' else 'video')
                
                asset_data = {
                    'filename': filename,
                    'original_filename': meta.get('original_filename', filename),
                    'category': cat,
                    'url': f'/api/assets/{cat}/{api_key_hash}/{filename}',
                    'upload_time': meta.get('upload_time', ''),
                    'file_type': file_type,
                    'file_size': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                    'project': asset_project,
                    'episode': asset_episode
                }
                
                # 为视频添加封面图URL
                if file_type == 'video':
                    poster_filename = filename.rsplit('.', 1)[0] + '.jpg'
                    asset_data['poster_url'] = f'/api/assets/video-poster/{api_key_hash}/{poster_filename}'
                
                assets.append(asset_data)
        
        # 按上传时间排序（最新的在前面）
        assets.sort(key=lambda x: x.get('upload_time', ''), reverse=True)
        
        # 分页
        total = len(assets)
        start = (page - 1) * limit
        end = start + limit
        paged_assets = assets[start:end]
        has_more = end < total
        
        return jsonify({
            'success': True,
            'assets': paged_assets,
            'page': page,
            'limit': limit,
            'total': total,
            'has_more': has_more
        })
    
    except Exception as e:
        print(f"[ERROR] 获取资产列表失败: {e}")
        return error_response(f'获取失败: {str(e)}')


@asset_bp.route('/api/assets/delete', methods=['POST'])
@require_auth
def delete_asset():
    """删除资产"""
    try:
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        category = data.get('category')
        filename = data.get('filename')
        
        if not category or not filename:
            return error_response('缺少参数')
        
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        base_dir = category_dirs.get(category)
        if not base_dir:
            return error_response('无效的资产分类')
        
        user_dir = os.path.join(base_dir, api_key_hash)
        filepath = os.path.join(user_dir, filename)
        meta_path = filepath + '.meta.json'
        
        # 删除文件
        if os.path.exists(filepath):
            os.remove(filepath)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        # 如果是视频，同时删除封面图
        if category == 'video':
            poster_filename = filename.rsplit('.', 1)[0] + '.jpg'
            poster_path = os.path.join(user_dir, 'posters', poster_filename)
            if os.path.exists(poster_path):
                os.remove(poster_path)
        
        return success_response('删除成功')
    
    except Exception as e:
        print(f"[ERROR] 删除资产失败: {e}")
        return error_response(f'删除失败: {str(e)}')


@asset_bp.route('/api/assets/update-tags', methods=['POST'])
@require_auth
def update_asset_tags():
    """更新单个资产的标签"""
    try:
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        category = data.get('category')
        filename = data.get('filename')
        project = data.get('project', '')
        episode = data.get('episode', '')
        
        if not category or not filename:
            return error_response('缺少参数')
        
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        base_dir = category_dirs.get(category)
        if not base_dir:
            return error_response('无效的资产分类')
        
        user_dir = os.path.join(base_dir, api_key_hash)
        meta_path = os.path.join(user_dir, filename + '.meta.json')
        
        # 读取现有元数据
        meta_data = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        
        # 更新标签
        meta_data['project'] = project
        meta_data['episode'] = episode
        meta_data['filename'] = filename
        meta_data['category'] = category
        
        # 保存元数据
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        
        # 如果项目/分集不存在，自动添加到项目列表
        if project:
            project_service = ProjectService(api_key_hash)
            project_service.ensure_project_and_episode(project, episode)
        
        return success_response('标签更新成功')
    
    except Exception as e:
        print(f"[ERROR] 更新资产标签失败: {e}")
        return error_response(f'更新失败: {str(e)}')


@asset_bp.route('/api/assets/copy-to-upload', methods=['POST'])
@require_auth
def copy_asset_to_upload():
    """将资产复制到上传目录，用于各应用模块使用"""
    try:
        import shutil
        api_key_hash = get_api_key_hash()

        data = request.get_json()
        category = data.get('category')  # storyboard, artwork
        filename = data.get('filename')
        target_type = data.get('target_type', 'i2v')  # i2v, kf2v, i2i

        if not category or not filename:
            return error_response('缺少参数')

        # 只支持图片资产
        if category not in ['storyboard', 'artwork']:
            return error_response('只能从分镜库或原画库选择图片')

        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR
        }

        target_dirs = {
            'i2v': Config.UPLOAD_I2V_DIR,
            'kf2v': Config.UPLOAD_KF2V_DIR,
            'i2i': Config.UPLOAD_I2I_DIR
        }

        source_dir = os.path.join(category_dirs[category], api_key_hash)
        source_path = os.path.join(source_dir, filename)

        if not os.path.exists(source_path):
            return error_response('源文件不存在')

        target_base_dir = target_dirs.get(target_type, Config.UPLOAD_I2V_DIR)
        target_dir = os.path.join(target_base_dir, api_key_hash)
        os.makedirs(target_dir, exist_ok=True)

        # 生成新文件名
        ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'png'
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        new_filename = f"{timestamp}_{unique_id}.{ext}"

        target_path = os.path.join(target_dir, new_filename)
        shutil.copy2(source_path, target_path)

        # 构建URL
        url_prefixes = {
            'i2v': f'/api/image/i2v/{api_key_hash}/{new_filename}',
            'kf2v': f'/api/image/kf2v/{api_key_hash}/{new_filename}',
            'i2i': f'/api/image/i2i/{api_key_hash}/{new_filename}'
        }

        return jsonify({
            'success': True,
            'filename': new_filename,
            'url': url_prefixes.get(target_type, url_prefixes['i2v'])
        })

    except Exception as e:
        print(f"[ERROR] 复制资产失败: {e}")
        return error_response(f'复制失败: {str(e)}')


@asset_bp.route('/api/assets/save-from-output', methods=['POST'])
@require_auth
def save_to_asset_library():
    """将输出的图片/视频保存到资产库"""
    try:
        import shutil
        import requests
        api_key_hash = get_api_key_hash()

        data = request.get_json()
        source_type = data.get('source_type')  # i2v, kf2v, t2i, i2i
        filename = data.get('filename')  # 文件名或URL
        target_category = data.get('target_category')  # storyboard, artwork, video
        file_type = data.get('file_type', 'image')  # image 或 video

        if not source_type or not filename or not target_category:
            return error_response('缺少参数')

        # 验证目标分类与文件类型是否匹配
        if file_type == 'video' and target_category != 'video':
            return error_response('视频只能保存到视频库')
        if file_type == 'image' and target_category == 'video':
            return error_response('图片不能保存到视频库')

        target_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }

        target_base_dir = target_dirs.get(target_category)
        if not target_base_dir:
            return error_response('无效的目标分类')

        target_dir = os.path.join(target_base_dir, api_key_hash)
        os.makedirs(target_dir, exist_ok=True)

        # 检查是否是URL（文生图的远程URL）
        is_remote_url = filename.startswith('http://') or filename.startswith('https://')
        
        # 检查是否是本地API URL，需要提取真正的文件名
        is_local_api_url = filename.startswith('/api/')
        if is_local_api_url:
            filename = filename.split('/')[-1]
        
        # 生成新文件名
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        if is_remote_url:
            # 从远程URL下载文件
            try:
                response = requests.get(filename, timeout=30)
                response.raise_for_status()
                
                # 从Content-Type推断扩展名
                content_type = response.headers.get('Content-Type', '')
                if 'png' in content_type:
                    ext = 'png'
                elif 'gif' in content_type:
                    ext = 'gif'
                elif 'webp' in content_type:
                    ext = 'webp'
                elif 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                else:
                    ext = 'png'
                
                new_filename = f"{timestamp}_{unique_id}.{ext}"
                target_path = os.path.join(target_dir, new_filename)
                
                with open(target_path, 'wb') as f:
                    f.write(response.content)
                    
            except Exception as e:
                print(f"[ERROR] 下载远程图片失败: {e}")
                return error_response(f'下载图片失败: {str(e)}')
        else:
            # 本地文件复制
            source_dirs = {
                'i2v': Config.OUTPUT_I2V_DIR,
                'kf2v': Config.OUTPUT_KF2V_DIR,
                't2i': Config.OUTPUT_T2I_DIR,
                'i2i': Config.OUTPUT_I2I_DIR,
                't2v': Config.OUTPUT_T2V_DIR,
                'r2v': Config.OUTPUT_R2V_DIR
            }
            
            source_base_dir = source_dirs.get(source_type)
            if not source_base_dir:
                return error_response('无效的源类型')

            source_path = os.path.join(source_base_dir, api_key_hash, filename)
            if not os.path.exists(source_path):
                return error_response('源文件不存在')

            ext = filename.rsplit('.', 1)[-1] if '.' in filename else ('mp4' if file_type == 'video' else 'png')
            new_filename = f"{timestamp}_{unique_id}.{ext}"
            target_path = os.path.join(target_dir, new_filename)
            shutil.copy2(source_path, target_path)

        # 保存元数据
        meta_filename = new_filename + '.meta.json'
        meta_path = os.path.join(target_dir, meta_filename)
        meta_data = {
            'original_filename': filename if not is_remote_url else filename.split('/')[-1],
            'filename': new_filename,
            'category': target_category,
            'upload_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'file_type': file_type,
            'source_type': source_type,
            'is_remote': is_remote_url
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)

        # 如果是视频，生成封面图
        if file_type == 'video':
            poster_dir = os.path.join(target_dir, 'posters')
            poster_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
            poster_path = os.path.join(poster_dir, poster_filename)
            generate_asset_video_poster(target_path, poster_path)

        return jsonify({
            'success': True,
            'filename': new_filename,
            'category': target_category,
            'url': f'/api/assets/{target_category}/{api_key_hash}/{new_filename}'
        })

    except Exception as e:
        print(f"[ERROR] 保存到资产库失败: {e}")
        return error_response(f'保存失败: {str(e)}')


@asset_bp.route('/api/assets/batch-tags', methods=['POST'])
@require_auth
def batch_update_tags():
    """批量更新资产标签"""
    try:
        api_key_hash = get_api_key_hash()
        
        data = request.get_json()
        assets = data.get('assets', [])  # [{category, filename}, ...]
        project = data.get('project', '')
        episode = data.get('episode', '')
        
        if not assets:
            return error_response('请选择要更新的资产')
        
        category_dirs = {
            'storyboard': Config.ASSETS_STORYBOARD_DIR,
            'artwork': Config.ASSETS_ARTWORK_DIR,
            'video': Config.ASSETS_VIDEO_DIR
        }
        
        updated_count = 0
        for asset in assets:
            category = asset.get('category')
            filename = asset.get('filename')
            
            if not category or not filename:
                continue
            
            base_dir = category_dirs.get(category)
            if not base_dir:
                continue
            
            user_dir = os.path.join(base_dir, api_key_hash)
            meta_path = os.path.join(user_dir, filename + '.meta.json')
            
            # 读取现有元数据
            meta_data = {}
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
            
            # 更新标签
            meta_data['project'] = project
            meta_data['episode'] = episode
            meta_data['filename'] = filename
            meta_data['category'] = category
            
            # 保存元数据
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            updated_count += 1
        
        # 如果项目/分集不存在，自动添加到项目列表
        if project:
            project_service = ProjectService(api_key_hash)
            project_service.ensure_project_and_episode(project, episode)
        
        return jsonify({
            'success': True,
            'message': f'成功更新 {updated_count} 个资产的标签'
        })
    
    except Exception as e:
        print(f"[ERROR] 批量更新标签失败: {e}")
        return error_response(f'更新失败: {str(e)}')
