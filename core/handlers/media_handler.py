"""媒体文件处理器"""
import os
import subprocess
from flask import request, Response, jsonify, send_file, make_response


class MediaHandler:
    """媒体文件处理器
    
    提取媒体文件服务的通用逻辑
    """
    
    @staticmethod
    def serve_video_with_range(filepath, mimetype='video/mp4'):
        """支持Range请求的视频服务
        
        解决NAS挂载目录读取慢的问题，实现：
        1. 分段传输 - 不用一次读取整个文件
        2. 进度条拖动 - 支持seek操作
        3. 浏览器缓存 - 减少重复请求
        4. 完整播放 - 支持完整视频流式加载
        
        Args:
            filepath: 视频文件路径
            mimetype: MIME类型
            
        Returns:
            Flask Response对象
        """
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404

        file_size = os.path.getsize(filepath)
        range_header = request.headers.get('Range', None)
        
        # print(f"[VIDEO DEBUG] 请求文件: {filepath}, 大小: {file_size}, Range: {range_header}")

        if range_header:
            # 处理Range请求
            byte_start, byte_end = 0, None

            match = range_header.replace('bytes=', '').split('-')
            if len(match) == 2:
                if match[0]:
                    byte_start = int(match[0])
                if match[1]:
                    byte_end = int(match[1])

            if byte_end is None:
                byte_end = file_size - 1
            else:
                byte_end = min(byte_end, file_size - 1)

            content_length = byte_end - byte_start + 1
            
            # print(f"[VIDEO DEBUG] Range解析: start={byte_start}, end={byte_end}, content_length={content_length}")

            def generate():
                bytes_sent = 0
                with open(filepath, 'rb') as f:
                    f.seek(byte_start)
                    remaining = content_length
                    chunk_size = 1024 * 1024  # 1MB
                    while remaining > 0:
                        read_size = min(chunk_size, remaining)
                        data = f.read(read_size)
                        if not data:
                            break
                        remaining -= len(data)
                        bytes_sent += len(data)
                        yield data
                # print(f"[VIDEO DEBUG] 流式传输完成: 已发送 {bytes_sent} 字节")

            response = Response(
                generate(),
                status=206,  # Partial Content
                mimetype=mimetype,
                direct_passthrough=True
            )
            response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
            response.headers['Content-Length'] = content_length
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['ETag'] = f'"{os.path.getmtime(filepath)}-{file_size}"'
            
            return response
        else:
            # 非Range请求，返回完整文件
            # print(f"[VIDEO DEBUG] 非Range请求，返回完整文件: {file_size} 字节")
            
            def generate_full():
                bytes_sent = 0
                with open(filepath, 'rb') as f:
                    chunk_size = 1024 * 1024  # 1MB块
                    while True:
                        data = f.read(chunk_size)
                        if not data:
                            break
                        bytes_sent += len(data)
                        yield data
                # print(f"[VIDEO DEBUG] 完整传输完成: 已发送 {bytes_sent} 字节")

            response = Response(
                generate_full(),
                status=200,
                mimetype=mimetype,
                direct_passthrough=True
            )
            response.headers['Content-Length'] = file_size
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['ETag'] = f'"{os.path.getmtime(filepath)}-{file_size}"'
            return response
    
    @staticmethod
    def serve_image(filepath, cache_days=30):
        """图片服务
        
        Args:
            filepath: 图片文件路径
            cache_days: 缓存天数（默认30天，与视频封面图一致）
            
        Returns:
            Flask Response对象
        """
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 检测MIME类型
        filename = os.path.basename(filepath)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
        mime_types = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'webp': 'image/webp',
            'bmp': 'image/bmp', 'gif': 'image/gif'
        }
        mimetype = mime_types.get(ext, 'image/png')

        response = make_response(send_file(filepath, mimetype=mimetype))
        response.headers['Cache-Control'] = f'public, max-age={cache_days * 86400}'
        response.headers['ETag'] = f'"{os.path.getmtime(filepath)}-{os.path.getsize(filepath)}"'
        return response
    
    @staticmethod
    def generate_video_poster(video_path, poster_path):
        """生成视频封面图
        
        使用ffmpeg提取视频帧作为封面
        
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
            
            # 使用ffmpeg提取第0.5秒的帧作为封面
            cmd = [
                'ffmpeg',
                '-ss', '0.5',
                '-i', video_path,
                '-vframes', '1',
                '-vf', 'scale=-1:360',  # 缩放高度为360px
                '-q:v', '3',  # 高质量JPEG
                '-y',
                poster_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0 and os.path.exists(poster_path):
                print(f"[INFO] 视频封面生成成功: {poster_path}")
                return True
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                print(f"[ERROR] 视频封面生成失败: {error_msg[:200]}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"[ERROR] ffmpeg超时: {video_path}")
            return False
        except Exception as e:
            print(f"[ERROR] 生成视频封面异常: {e}")
            return False
