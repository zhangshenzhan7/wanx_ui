import requests
import os
from pathlib import Path
from typing import Dict, Optional


class AudioService:
    """音频上传服务，用于获取DashScope OSS临时URL"""
    
    def __init__(self, api_key: str):
        """初始化音频服务
        
        Args:
            api_key: DashScope API Key
        """
        self.api_key = api_key
        self.upload_url = "https://dashscope.aliyuncs.com/api/v1/uploads"
    
    def get_upload_policy(self, model_name: str = "wanx-v1") -> Optional[Dict]:
        """获取文件上传凭证
        
        Args:
            model_name: 模型名称，默认wanx-v1
            
        Returns:
            上传凭证数据字典
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "action": "getPolicy",
                "model": model_name
            }
            
            response = requests.get(self.upload_url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                error_msg = f"获取上传凭证失败: {response.status_code}"
                try:
                    error_detail = response.json()
                    if error_detail.get('message'):
                        error_msg = f"{error_msg} - {error_detail['message']}"
                except:
                    pass
                print(f"[ERROR] {error_msg}")
                return None
            
            result = response.json()
            if result.get('data'):
                return result['data']
            
            return None
            
        except Exception as e:
            print(f"[ERROR] 获取上传凭证失败: {e}")
            return None
    
    def upload_file_to_oss(self, policy_data: Dict, file_path: str) -> Optional[str]:
        """将文件上传到临时存储OSS
        
        Args:
            policy_data: 上传凭证数据
            file_path: 本地文件路径
            
        Returns:
            OSS URL (oss://格式)
        """
        try:
            file_name = Path(file_path).name
            key = f"{policy_data['upload_dir']}/{file_name}"
            
            # 先读取文件内容到内存，避免文件句柄问题
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # 准备multipart/form-data
            files = {
                'key': (None, key),
                'OSSAccessKeyId': (None, policy_data['oss_access_key_id']),
                'policy': (None, policy_data['policy']),
                'Signature': (None, policy_data['signature']),
                'x-oss-object-acl': (None, policy_data['x_oss_object_acl']),
                'x-oss-forbid-overwrite': (None, policy_data['x_oss_forbid_overwrite']),
                'success_action_status': (None, '200'),
                'file': (file_name, file_content, 'application/octet-stream')
            }
            
            # 使用更长的超时时间
            response = requests.post(
                policy_data['upload_host'], 
                files=files, 
                timeout=(30, 120)  # (连接超时, 读取超时)
            )
            
            if response.status_code != 200:
                error_msg = f"上传文件失败: {response.status_code}"
                print(f"[ERROR] {error_msg}")
                print(f"[ERROR] Response: {response.text}")
                return None
            
            oss_url = f"oss://{key}"
            print(f"[INFO] 文件上传成功: {oss_url}")
            return oss_url
            
        except requests.exceptions.Timeout as e:
            print(f"[ERROR] 上传文件超时: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] 网络连接失败: {e}")
            print(f"[INFO] 请检查网络连接，或稍后重试")
            return None
        except Exception as e:
            print(f"[ERROR] 上传文件到OSS失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def upload_audio_and_get_url(self, file_path: str, model_name: str = "wanx-v1") -> Optional[str]:
        """上传音频文件并获取OSS临时URL
        
        Args:
            file_path: 本地音频文件路径
            model_name: 模型名称
            
        Returns:
            OSS URL (oss://格式)，有效期48小时
        """
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # 1. 获取上传凭证
                policy_data = self.get_upload_policy(model_name)
                if not policy_data:
                    if attempt < max_retries - 1:
                        print(f"[WARN] 获取上传凭证失败，{retry_delay}秒后重试... ({attempt + 1}/{max_retries})")
                        import time
                        time.sleep(retry_delay)
                        continue
                    return None
                
                # 2. 上传文件到OSS
                oss_url = self.upload_file_to_oss(policy_data, file_path)
                
                if oss_url:
                    return oss_url
                elif attempt < max_retries - 1:
                    print(f"[WARN] 上传失败，{retry_delay}秒后重试... ({attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    continue
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[WARN] 上传音频失败: {e}，{retry_delay}秒后重试... ({attempt + 1}/{max_retries})")
                    import time
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"[ERROR] 上传音频最终失败: {e}")
                    return None
        
        return None
    
    def validate_audio_file(self, file_path: str) -> tuple[bool, str]:
        """验证音频文件
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        # 检查文件大小 (最大15MB)
        file_size = os.path.getsize(file_path)
        max_size = 15 * 1024 * 1024  # 15MB
        if file_size > max_size:
            return False, f"文件大小超过限制(最大15MB)，当前: {file_size / 1024 / 1024:.2f}MB"
        
        # 检查文件格式
        ext = Path(file_path).suffix.lower()
        allowed_formats = ['.wav', '.mp3']
        if ext not in allowed_formats:
            return False, f"不支持的音频格式，仅支持: {', '.join(allowed_formats)}"
        
        return True, ""
