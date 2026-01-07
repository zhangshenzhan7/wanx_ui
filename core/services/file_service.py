"""文件处理服务"""
import os
import time
import uuid
from config import Config


class FileService:
    """文件处理服务
    
    负责文件的上传、保存、验证等操作
    """
    
    def __init__(self, api_key_hash):
        """初始化文件服务
        
        Args:
            api_key_hash: 用户API Key哈希值
        """
        self.api_key_hash = api_key_hash
    
    def upload_file(self, file, upload_type, frame_type=None):
        """统一的文件上传接口
        
        Args:
            file: Flask上传的文件对象
            upload_type: 上传类型（i2v_image, i2i_image, kf2v_image, r2v_video, audio, asset）
            frame_type: 帧类型（仅用于kf2v，'first'或'last'）
            
        Returns:
            成功时返回 (True, {'filename': xxx, 'url': xxx})
            失败时返回 (False, error_message)
        """
        if not file or file.filename == '':
            return False, '没有选择文件'
        
        # 获取文件扩展名
        original_filename = file.filename
        ext = ''
        if '.' in original_filename:
            ext = original_filename.rsplit('.', 1)[1].lower()
        
        # 生成新文件名
        new_filename = self.generate_unique_filename(original_filename, frame_type)
        
        # 获取上传目录
        upload_dir = self.get_upload_dir(upload_type)
        if not upload_dir:
            return False, '无效的上传类型'
        
        # 创建用户目录
        user_dir = os.path.join(upload_dir, self.api_key_hash)
        os.makedirs(user_dir, exist_ok=True)
        
        # 保存文件
        filepath = os.path.join(user_dir, new_filename)
        try:
            file.save(filepath)
            
            # 同步到磁盘
            try:
                if hasattr(os, 'sync'):
                    os.sync()
            except:
                pass
            
            # 构建URL
            url = self.build_file_url(upload_type, new_filename, frame_type)
            
            return True, {'filename': new_filename, 'url': url}
            
        except Exception as e:
            return False, f'文件保存失败: {str(e)}'
    
    def generate_unique_filename(self, original_filename, prefix=None):
        """生成唯一文件名
        
        Args:
            original_filename: 原始文件名
            prefix: 前缀（可选）
            
        Returns:
            新文件名
        """
        ext = ''
        if '.' in original_filename:
            ext = original_filename.rsplit('.', 1)[1].lower()
        
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        if prefix:
            filename = f"{timestamp}_{unique_id}_{prefix}.{ext}" if ext else f"{timestamp}_{unique_id}_{prefix}"
        else:
            filename = f"{timestamp}_{unique_id}.{ext}" if ext else f"{timestamp}_{unique_id}"
        
        return filename
    
    def get_upload_dir(self, upload_type):
        """获取上传目录
        
        Args:
            upload_type: 上传类型
            
        Returns:
            上传目录路径或None
        """
        upload_dirs = {
            'i2v_image': Config.UPLOAD_I2V_DIR,
            'i2i_image': Config.UPLOAD_I2I_DIR,
            'kf2v_image': Config.UPLOAD_KF2V_DIR,
            'r2v_video': Config.UPLOAD_R2V_DIR,
            'audio': Config.UPLOAD_AUDIO_DIR,
            'voice_audio': Config.UPLOAD_VOICE_DIR,
            'asset_storyboard': Config.ASSETS_STORYBOARD_DIR,
            'asset_artwork': Config.ASSETS_ARTWORK_DIR,
            'asset_video': Config.ASSETS_VIDEO_DIR
        }
        return upload_dirs.get(upload_type)
    
    def get_output_dir(self, output_type):
        """获取输出目录
        
        Args:
            output_type: 输出类型
            
        Returns:
            输出目录路径或None
        """
        output_dirs = {
            'i2v': Config.OUTPUT_I2V_DIR,
            't2v': Config.OUTPUT_T2V_DIR,
            't2i': Config.OUTPUT_T2I_DIR,
            'i2i': Config.OUTPUT_I2I_DIR,
            'kf2v': Config.OUTPUT_KF2V_DIR,
            'r2v': Config.OUTPUT_R2V_DIR,
            'voice': Config.OUTPUT_VOICE_DIR
        }
        return output_dirs.get(output_type)
    
    def build_file_url(self, upload_type, filename, frame_type=None):
        """构建文件URL
        
        Args:
            upload_type: 上传类型
            filename: 文件名
            frame_type: 帧类型（可选）
            
        Returns:
            文件URL
        """
        url_patterns = {
            'i2v_image': f'/api/image/i2v/{self.api_key_hash}/{filename}',
            'i2i_image': f'/api/image/i2i/{self.api_key_hash}/{filename}',
            'kf2v_image': f'/api/image/kf2v/{self.api_key_hash}/{filename}',
            'r2v_video': f'/api/video/r2v/{self.api_key_hash}/{filename}',
            'audio': f'/api/audio/{self.api_key_hash}/{filename}',
            'voice_audio': f'/api/voice/audio/{self.api_key_hash}/{filename}',
        }
        
        if upload_type.startswith('asset_'):
            category = upload_type.replace('asset_', '')
            return f'/api/assets/{category}/{self.api_key_hash}/{filename}'
        
        return url_patterns.get(upload_type, f'/api/file/{self.api_key_hash}/{filename}')
    
    def validate_file(self, file, allowed_extensions):
        """验证文件类型和大小
        
        Args:
            file: 上传的文件对象
            allowed_extensions: 允许的扩展名集合
            
        Returns:
            (is_valid, error_message)
        """
        if not file or file.filename == '':
            return False, '没有选择文件'
        
        filename = file.filename
        if '.' not in filename:
            return False, '无效的文件名'
        
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_extensions:
            return False, f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
        
        return True, None
    
    def copy_file(self, source_path, target_type, target_filename=None):
        """复制文件到目标目录
        
        Args:
            source_path: 源文件路径
            target_type: 目标类型（i2v_image等）
            target_filename: 目标文件名（可选，不提供则自动生成）
            
        Returns:
            (success, result) - result为新文件名或错误信息
        """
        import shutil
        
        if not os.path.exists(source_path):
            return False, '源文件不存在'
        
        target_dir = self.get_upload_dir(target_type)
        if not target_dir:
            return False, '无效的目标类型'
        
        user_dir = os.path.join(target_dir, self.api_key_hash)
        os.makedirs(user_dir, exist_ok=True)
        
        if not target_filename:
            original_filename = os.path.basename(source_path)
            target_filename = self.generate_unique_filename(original_filename)
        
        target_path = os.path.join(user_dir, target_filename)
        
        try:
            shutil.copy2(source_path, target_path)
            return True, target_filename
        except Exception as e:
            return False, f'文件复制失败: {str(e)}'
