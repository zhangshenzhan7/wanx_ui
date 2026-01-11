import requests
import base64
import time
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional, List, Callable
from functools import lru_cache
from config import Config

try:
    from gevent.pool import Pool as GeventPool
except ImportError:
    GeventPool = None

# 全局线程池用于后台任务
_background_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix='qwen_image_edit_')

# 后台任务回调注册表
_task_callbacks: Dict[str, Callable] = {}


class VideoService:
    """通义万相视频生成服务"""

    # 类级别的HTTP连接池(所有实例共享)
    _session_pool = {}

    # 类级别的任务状态缓存(LRU,最多缓存1000个任务)
    _task_cache_size = 1000

    def __init__(self, api_key: str):
        """初始化视频服务

        Args:
            api_key: DashScope API Key
        """
        self.api_key = api_key
        self.session = self._get_or_create_session()

        # 初始化任务状态缓存
        if not hasattr(self.__class__, '_task_status_cache'):
            self.__class__._task_status_cache = {}

    @classmethod
    def _get_or_create_session(cls) -> requests.Session:
        """获取或创建HTTP会话(连接池复用)"""
        # 使用线程安全的session池
        import threading
        thread_id = threading.current_thread().ident

        if thread_id not in cls._session_pool:
            session = requests.Session()
            # 配置连接池参数
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,  # 连接池大小
                pool_maxsize=50,  # 最大连接数
                max_retries=3,  # 自动重试
                pool_block=False
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            cls._session_pool[thread_id] = session

        return cls._session_pool[thread_id]

    def _cache_task_status(self, task_id: str, status: Dict):
        """缓存任务状态(L1内存缓存)"""
        # LRU淘汰策略:如果缓存满了,删除最旧的条目
        if len(self._task_status_cache) >= self._task_cache_size:
            # 简单FIFO淘汰(可优化为LRU)
            oldest_key = next(iter(self._task_status_cache))
            del self._task_status_cache[oldest_key]

        self._task_status_cache[task_id] = {
            'data': status,
            'timestamp': time.time()
        }

    def _get_cached_task_status(self, task_id: str, ttl: int = 5) -> Optional[Dict]:
        """从缓存获取任务状态

        Args:
            task_id: 任务ID
            ttl: 缓存有效期(秒),默认5秒
        """
        cached = self._task_status_cache.get(task_id)
        if cached:
            # 检查是否过期
            if time.time() - cached['timestamp'] < ttl:
                return cached['data']
            else:
                # 过期删除
                del self._task_status_cache[task_id]
        return None

    def create_task(self, image_path: str, prompt: str = '', model: str = 'wan2.6-i2v',
                    resolution: str = '720P', duration: int = 5, audio_url: str = '',
                    negative_prompt: str = '', prompt_extend: bool = True,
                    shot_type: str = 'single',
                    watermark: bool = False, audio: bool = False) -> Optional[Dict]:
        """创建视频生成任务

        Args:
            image_path: 图片文件路径
            prompt: 提示词
            model: 模型名称
            resolution: 分辨率
            duration: 时长（秒）
            audio_url: 音频URL
            negative_prompt: 反向提示词
            prompt_extend: 是否启用智能改写
            watermark: 是否添加水印

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # 将图片编码为Base64
            image_base64 = self.encode_image_to_base64(image_path)

            # 构建请求参数 - 使用img_url字段(支持Base64)
            params = {
                'model': model,
                'input': {
                    'img_url': image_base64  # API要求的字段名是img_url,支持Base64
                },
                'parameters': {}
            }

            # 添加可选参数
            if prompt:
                params['input']['prompt'] = prompt

            if resolution:
                params['parameters']['resolution'] = resolution

            if duration:
                params['parameters']['duration'] = duration

            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt

            if prompt_extend is not None:
                params['parameters']['prompt_extend'] = prompt_extend

            # wan2.6-i2v 支持镜头类型参数，仅在启用prompt_extend时生效
            if model == 'wan2.6-i2v' and prompt_extend and shot_type:
                params['parameters']['shot_type'] = shot_type

            if watermark is not None:
                params['parameters']['watermark'] = watermark

            # wan2.6-i2v 和 wan2.5-i2v-preview模型支持audio参数
            if model == 'wan2.6-i2v' or model == 'wan2.5-i2v-preview':
                # 如果提供了audio_url,则使用自定义音频（放在input中）
                if audio_url:
                    params['input']['audio_url'] = audio_url
                else:
                    # 否则使用audio参数控制是否自动配音
                    params['parameters']['audio'] = audio

            # 调试日志
            print(f"[DEBUG] Creating task: model={model}, img_url_length={len(image_base64)} chars")

            # 调用API(使用连接池)
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/video-generation/video-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable',
                'X-DashScope-OssResourceResolve': 'enable',
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 提取任务信息
            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),  # 使用task_status而不是status
                    'prompt': prompt,
                    'model': model,
                    'resolution': resolution,
                    'duration': duration,
                    'audio_url': audio_url,
                    'negative_prompt': negative_prompt,
                    'prompt_extend': prompt_extend,
                    'shot_type': shot_type,
                    'watermark': watermark,
                    'audio': audio,
                    'request_id': result.get('request_id')
                }
                return task_info

            # 如果API返回了错误信息
            error_msg = result.get('message', '未知错误')
            print(f"创建任务失败: {error_msg}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
            except:
                pass
            print(f"创建任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"创建任务失败: {e}")
            return None

    def get_task_status(self, task_id: str, use_cache: bool = True) -> Optional[Dict]:
        """查询任务状态

        Args:
            task_id: 任务ID
            use_cache: 是否使用L1缓存

        Returns:
            任务状态信息
        """
        # 先检查缓存
        if use_cache:
            cached = self._get_cached_task_status(task_id)
            if cached:
                return cached

        try:
            url = f"{Config.DASHSCOPE_BASE_URL}/tasks/{task_id}"
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }

            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()

            # 提取任务状态信息
            if result.get('output'):
                output = result['output']
                task_info = {
                    'task_id': task_id,
                    'task_status': output.get('task_status', 'UNKNOWN'),
                    'video_url': output.get('video_url', ''),
                    'code': result.get('code', ''),
                    'message': result.get('message', '')
                }
                        
                # 记录异常情况：任务成功但没有结果
                if task_info['task_status'] == 'SUCCEEDED' and not task_info['video_url']:
                    print(f"[WARN] 任务状态为SUCCEEDED但没有video_url: task_id={task_id}")
                    print(f"[WARN] 完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    # 检查是否有错误信息
                    if result.get('code') or result.get('message'):
                        print(f"[WARN] API返回错误: code={result.get('code')}, message={result.get('message')}")
                        task_info['task_status'] = 'FAILED'  # 将状态修正为失败
                        task_info['message'] = result.get('message', '生成失败，未返回视频URL')

                # wan2.6-image / wan2.6-t2i 特殊处理：从 choices[].message.content[] 提取图片URLs
                if result['output'].get('choices'):
                    results = []
                    for choice in result['output']['choices']:
                        message = choice.get('message', {})
                        content = message.get('content', [])
                        for item in content:
                            if isinstance(item, dict) and item.get('image'):
                                results.append({'url': item['image']})
                    if results:
                        task_info['results'] = results
                        print(f"[DEBUG] wan2.6-image异步任务提取到 {len(results)} 张图片")
                # 其他模型：提取 results 字段
                elif result['output'].get('results'):
                    task_info['results'] = result['output']['results']

                # 如果任务失败,记录完成时间
                if task_info['task_status'] in ['FAILED', 'SUCCEEDED', 'CANCELED']:
                    task_info['end_time'] = datetime.now().isoformat()

                # 缓存任务状态
                if use_cache:
                    self._cache_task_status(task_id, task_info)

                return task_info

            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if error_detail.get('message'):
                    error_msg = error_detail['message']
            except:
                pass
            print(f"查询任务状态失败: {error_msg}")
            return None
        except Exception as e:
            print(f"查询任务状态失败: {e}")
            return None

    def encode_image_to_base64(self, image_path: str) -> str:
        """将图片编码为Base64，带重试机制"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # OSS挂载目录可能需要等待文件同步
                if not os.path.exists(image_path):
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    else:
                        raise FileNotFoundError(f"图片文件不存在: {image_path}")

                with open(image_path, 'rb') as f:
                    image_data = f.read()

                # 检测MIME类型
                ext = image_path.rsplit('.', 1)[1].lower()
                mime_types = {
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'png': 'image/png',
                    'bmp': 'image/bmp',
                    'webp': 'image/webp'
                }
                mime_type = mime_types.get(ext, 'image/jpeg')

                encoded = base64.b64encode(image_data).decode('utf-8')
                return f"data:{mime_type};base64,{encoded}"

            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    print(f"[WARN] 读取图片失败，第{attempt + 1}次重试: {e}")
                    time.sleep(0.2 * (attempt + 1))
                else:
                    print(f"[ERROR] 读取图片最终失败: {e}")
                    raise

    def verify_api_key(self) -> bool:
        """验证API Key是否有效

        Returns:
            True表示有效，False表示无效
        """
        try:
            # 尝试获取一个不存在的任务，如果返回401则说明API Key无效
            url = f"{Config.DASHSCOPE_BASE_URL}/tasks/test-validation"
            headers = {'Authorization': f'Bearer {self.api_key}'}
            response = self.session.get(url, headers=headers, timeout=10)

            # 如果是401，说明API Key无效
            if response.status_code == 401:
                return False

            # 其他情况（包括404）都说明API Key是有效的
            return True
        except Exception as e:
            print(f"验证API Key失败: {e}")
            return False

    def create_kf2v_task(self, first_frame_path: str, last_frame_path: str,
                         prompt: str, model: str = 'wan2.2-kf2v-flash',
                         resolution: str = '720P',
                         negative_prompt: str = '', prompt_extend: bool = True) -> Optional[Dict]:
        """创建首尾帧生视频任务

        Args:
            first_frame_path: 首帧图片路径
            last_frame_path: 尾帧图片路径
            prompt: 提示词
            model: 模型名称
            resolution: 分辨率
            negative_prompt: 反向提示词
            prompt_extend: 是否启用智能改写

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # 将首帧编码为Base64
            first_frame_base64 = self.encode_image_to_base64(first_frame_path)

            # 将尾帧编码为Base64
            last_frame_base64 = self.encode_image_to_base64(last_frame_path)

            # 构建请求参数
            params = {
                'model': model,
                'input': {
                    'first_frame_url': first_frame_base64,
                    'last_frame_url': last_frame_base64,
                    'prompt': prompt
                },
                'parameters': {}
            }

            # 添加参数
            if resolution:
                params['parameters']['resolution'] = resolution

            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt

            if prompt_extend is not None:
                params['parameters']['prompt_extend'] = prompt_extend

            # 调试日志
            print(f"[DEBUG] Creating kf2v task: model={model}, resolution={resolution}")

            # 调用DashScope首尾帧生视频API(使用连接池)
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/image2video/video-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 提取任务信息
            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 'kf2v',
                    'prompt': prompt,
                    'model': model,
                    'resolution': resolution,
                    'negative_prompt': negative_prompt,
                    'prompt_extend': prompt_extend,
                    'create_time': datetime.now().isoformat(),
                    'request_id': result.get('request_id')
                }
                return task_info

            # 如果API返回了错误信息
            error_msg = result.get('message', '未知错误')
            print(f"[ERROR] 创建首尾帧任务失败: {error_msg}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
            except:
                pass
            print(f"[ERROR] 创建首尾帧任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建首尾帧任务失败: {e}")
            return None

    def upload_file_to_dashscope(self, file_path: str, model: str) -> Optional[str]:
        """上传文件到DashScope临时存储并获取URL
        
        Args:
            file_path: 本地文件路径
            model: 模型名称（如wan2.6-r2v）
            
        Returns:
            OSS临时URL（oss://开头），有效期48小时
        """
        try:
            import os
            from pathlib import Path
            
            # 1. 获取上传凭证
            url = "https://dashscope.aliyuncs.com/api/v1/uploads"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            params = {
                'action': 'getPolicy',
                'model': model
            }
            
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if not result.get('data'):
                print(f"[ERROR] 获取上传凭证失败: {result}")
                return None
                
            policy_data = result['data']
            
            # 2. 上传文件到OSS
            file_name = Path(file_path).name
            key = f"{policy_data['upload_dir']}/{file_name}"
            
            with open(file_path, 'rb') as file:
                files = {
                    'OSSAccessKeyId': (None, policy_data['oss_access_key_id']),
                    'Signature': (None, policy_data['signature']),
                    'policy': (None, policy_data['policy']),
                    'x-oss-object-acl': (None, policy_data['x_oss_object_acl']),
                    'x-oss-forbid-overwrite': (None, policy_data['x_oss_forbid_overwrite']),
                    'key': (None, key),
                    'success_action_status': (None, '200'),
                    'file': (file_name, file)
                }
                
                upload_response = self.session.post(
                    policy_data['upload_host'], 
                    files=files,
                    timeout=180  # 上传视频可能需要较长时间
                )
                
                if upload_response.status_code != 200:
                    print(f"[ERROR] 上传文件失败: {upload_response.text}")
                    return None
            
            oss_url = f"oss://{key}"
            print(f"[INFO] 文件上传成功: {file_name} -> {oss_url}")
            return oss_url
            
        except Exception as e:
            print(f"[ERROR] 上传文件到DashScope失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_r2v_task(self, reference_video_paths: List[str],
                        prompt: str, model: str = 'wan2.6-r2v',
                        size: str = '1280*720', duration: int = 5,
                        shot_type: str = 'single',
                        negative_prompt: str = '', seed: int = None,
                        watermark: bool = False, audio: bool = True) -> Optional[Dict]:
        """创建参考生视频任务

        Args:
            reference_video_paths: 参考视频路径列表（最多3个）
            prompt: 提示词，使用character1指代第一个参考视频主体，character2指代第二个，character3指代第三个
            model: 模型名称
            size: 视频分辨率（1280*720、1920*1080）
            duration: 时长（秒），5或10
            shot_type: 镜头类型（single、multi）
            negative_prompt: 反向提示词
            seed: 随机数种子
            watermark: 是否添加水印
            audio: 是否启用自动配音（默认True）

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # 将参考视频上传到DashScope临时存储获取URL
            reference_video_urls = []
            for video_path in reference_video_paths[:3]:  # 最多3个视频
                # 上传视频到DashScope并获取临时URL
                oss_url = self.upload_file_to_dashscope(video_path, model)
                if not oss_url:
                    print(f"[ERROR] 上传参考视频失败: {video_path}")
                    return None
                reference_video_urls.append(oss_url)

            # 构建请求参数
            params = {
                'model': model,
                'input': {
                    'prompt': prompt
                },
                'parameters': {}
            }

            # 添加参考视频URL（如果有）
            if reference_video_urls:
                params['input']['reference_video_urls'] = reference_video_urls

            # 添加可选参数到input
            if negative_prompt:
                params['input']['negative_prompt'] = negative_prompt
            
            # 添加可选参数到parameters
            if size:
                params['parameters']['size'] = size

            if duration:
                params['parameters']['duration'] = duration

            if shot_type:
                params['parameters']['shot_type'] = shot_type
            
            # 音频参数（wan2.6-r2v支持）
            if audio is not None:
                params['parameters']['audio'] = audio

            if seed is not None:
                params['parameters']['seed'] = seed

            if watermark is not None:
                params['parameters']['watermark'] = watermark

            # 调试日志
            print(f"[DEBUG] Creating r2v task: model={model}, size={size}, duration={duration}, shot_type={shot_type}, audio={audio}")
            print(f"[DEBUG] Reference video URLs: {reference_video_urls}")

            # 调用DashScope参考生视频API
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/video-generation/video-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable',
                'X-DashScope-OssResourceResolve': 'enable'  # 支持oss://格式的URL
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 提取任务信息
            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 'r2v',
                    'prompt': prompt,
                    'model': model,
                    'size': size,
                    'duration': duration,
                    'shot_type': shot_type,
                    'negative_prompt': negative_prompt,
                    'seed': seed,
                    'watermark': watermark,
                    'audio': audio,
                    'create_time': datetime.now().isoformat(),
                    'request_id': result.get('request_id')
                }
                return task_info

            # 如果API返回了错误信息
            error_msg = result.get('message', '未知错误')
            print(f"[ERROR] 创建参考生视频任务失败: {error_msg}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
            except:
                pass
            print(f"[ERROR] 创建参考生视频任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建参考生视频任务失败: {e}")
            return None

    def create_tasks_batch(self, tasks_params: List[Dict]) -> List[Optional[Dict]]:
        """批量并发创建任务(使用gevent协程池)

        Args:
            tasks_params: 任务参数列表,每个元素包含create_task的参数

        Returns:
            任务信息列表
        """
        if not GeventPool:
            # 如果gevent不可用,降级为串行创建
            print("[WARN] gevent不可用,使用串行方式创建任务")
            return [self._create_task_from_dict(params) for params in tasks_params]

        # 使用gevent协程池并发创建
        pool = GeventPool(size=min(len(tasks_params), 10))  # 最多10个并发
        results = pool.map(self._create_task_from_dict, tasks_params)
        pool.join()

        return list(results)

    def _create_task_from_dict(self, params: Dict) -> Optional[Dict]:
        """从参数字典创建任务(供批量创建使用)"""
        task_type = params.get('task_type', 'i2v')

        if task_type == 'kf2v':
            return self.create_kf2v_task(
                first_frame_path=params['first_frame_path'],
                last_frame_path=params['last_frame_path'],
                prompt=params['prompt'],
                model=params.get('model', 'wan2.2-kf2v-flash'),
                resolution=params.get('resolution', '720P'),
                negative_prompt=params.get('negative_prompt', ''),
                prompt_extend=params.get('prompt_extend', True)
            )
        else:
            return self.create_task(
                image_path=params['image_path'],
                prompt=params.get('prompt', ''),
                model=params.get('model', 'wan2.6-i2v'),
                resolution=params.get('resolution', '720P'),
                duration=params.get('duration', 5),
                audio_url=params.get('audio_url', ''),
                negative_prompt=params.get('negative_prompt', ''),
                prompt_extend=params.get('prompt_extend', True),
                watermark=params.get('watermark', False),
                audio=params.get('audio', True)
            )

    def create_t2i_task(self, prompt: str, model: str = 'wan2.5-t2i-preview',
                        size: str = '1024*1024', n: int = 1,
                        negative_prompt: str = '',
                        prompt_extend: bool = True,
                        watermark: bool = False,
                        callback: Callable = None) -> Optional[Dict]:
        """创建文生图任务

        Args:
            prompt: 提示词
            model: 模型名称
            size: 图片尺寸
            n: 生成数量
            negative_prompt: 反向提示词
            prompt_extend: 是否启用智能改写（默认True）
            watermark: 是否添加水印（默认False）
            callback: 后台任务完成后的回调函数（仅wan2.6-t2i使用）

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # wan2.6-t2i 使用新的API格式（模拟异步接口）
            if model == 'wan2.6-t2i':
                return self._create_wan26_t2i_task(prompt, size, n, negative_prompt, prompt_extend, watermark, callback)
            
            # z-image-turbo 使用同步API（模拟异步接口）
            if model == 'z-image-turbo':
                return self._create_z_image_task(prompt, size, n, negative_prompt, prompt_extend, watermark, callback)
            
            # 旧版模型使用异步API
            params = {
                'model': model,
                'input': {
                    'prompt': prompt
                },
                'parameters': {
                    'size': size,
                    'n': n
                }
            }

            # 添加智能改写参数
            if prompt_extend is not None:
                params['parameters']['prompt_extend'] = prompt_extend

            # qwen-image-plus 模型需要额外参数
            if model == 'qwen-image-plus':
                params['parameters']['watermark'] = False

            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt

            print(f"[DEBUG] Creating t2i task: model={model}, size={size}, n={n}")
            print(f"[DEBUG] Request params: {params}")

            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/text2image/image-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)

            # 打印响应状态和内容
            print(f"[DEBUG] Response status: {response.status_code}")
            result = response.json()
            print(f"[DEBUG] Response body: {result}")

            # 打印 request_id
            if result.get('request_id'):
                print(f"[INFO] Request ID: {result['request_id']}")

            response.raise_for_status()

            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 't2i',
                    'prompt': prompt,
                    'model': model,
                    'size': size,
                    'n': n,
                    'negative_prompt': negative_prompt,
                    'prompt_extend': prompt_extend,
                    'request_id': result.get('request_id'),
                    'create_time': datetime.now().isoformat()
                }
                print(
                    f"[INFO] Task created successfully: {task_info['task_id']}, request_id: {task_info.get('request_id')}")
                return task_info

            error_msg = result.get('message', '未知错误')
            error_code = result.get('code', 'UNKNOWN')
            print(
                f"[ERROR] 创建文生图任务失败: code={error_code}, message={error_msg}, request_id={result.get('request_id')}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                request_id = error_detail.get('request_id', 'N/A')
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
                print(f"[ERROR] 创建文生图任务失败: {error_msg}, request_id: {request_id}")
            except:
                print(f"[ERROR] 创建文生图任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建文生图任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_wan26_t2i_task(self, prompt: str, size: str, n: int,
                               negative_prompt: str, prompt_extend: bool,
                               watermark: bool, callback: Callable = None) -> Optional[Dict]:
        """创建wan2.6-t2i任务（模拟异步）
        
        wan2.6-t2i使用同步接口，但为了保持用户体验一致：
        1. 立即返回PENDING状态的任务信息
        2. 在后台线程中执行实际的API请求
        3. 完成后更新任务状态
        
        Args:
            prompt: 提示词
            size: 图片尺寸
            n: 生成数量（1-4张）
            negative_prompt: 反向提示词
            prompt_extend: 是否启用智能改写
            watermark: 是否添加水印
            callback: 后台任务完成后的回调函数
            
        Returns:
            任务信息字典（PENDING状态）
        """
        import uuid
        
        # 生成唯一任务ID
        task_id = f"wan26_{uuid.uuid4().hex[:16]}"
        
        # 立即返回PENDING状态的任务信息
        task_info = {
            'task_id': task_id,
            'task_status': 'PENDING',
            'task_type': 't2i',
            'prompt': prompt,
            'model': 'wan2.6-t2i',
            'size': size,
            'n': n,
            'negative_prompt': negative_prompt,
            'prompt_extend': prompt_extend,
            'watermark': watermark,
            'create_time': datetime.now().isoformat()
        }
        
        # 在后台线程中执行实际的API调用
        def execute_task():
            try:
                print(f"[INFO] 后台执行wan2.6-t2i任务: {task_id}")
                result = self._execute_wan26_t2i_api(prompt, size, n, negative_prompt, prompt_extend, watermark)
                
                if result:
                    # 更新任务状态
                    update_data = {
                        'task_status': 'SUCCEEDED',
                        'image_urls': result.get('image_urls', []),
                        'request_id': result.get('request_id'),
                        'usage': result.get('usage', {})
                    }
                    print(f"[INFO] wan2.6-t2i任务完成: {task_id}, {len(update_data['image_urls'])} 张图片")
                else:
                    update_data = {
                        'task_status': 'FAILED',
                        'message': '图片生成失败'
                    }
                    print(f"[ERROR] wan2.6-t2i任务失败: {task_id}")
                
                # 调用回调函数更新缓存
                if callback:
                    callback(task_id, update_data)
                    
            except Exception as e:
                print(f"[ERROR] wan2.6-t2i后台任务执行失败: {task_id}, {e}")
                if callback:
                    callback(task_id, {
                        'task_status': 'FAILED',
                        'message': str(e)
                    })
        
        # 提交到后台线程池
        _background_executor.submit(execute_task)
        
        return task_info
    
    def _execute_wan26_t2i_api(self, prompt: str, size: str, n: int,
                               negative_prompt: str, prompt_extend: bool,
                               watermark: bool) -> Optional[Dict]:
        """执行wan2.6-t2i API调用（同步）
        
        Args:
            prompt: 提示词
            size: 图片尺寸
            n: 生成数量（1-4张）
            negative_prompt: 反向提示词
            prompt_extend: 是否启用智能改写
            watermark: 是否添加水印
            
        Returns:
            包含image_urls的结果字典
        """
        try:
            # 构建wan2.6-t2i的请求参数（使用messages格式）
            params = {
                'model': 'wan2.6-t2i',
                'input': {
                    'messages': [
                        {
                            'role': 'user',
                            'content': [
                                {
                                    'text': prompt
                                }
                            ]
                        }
                    ]
                },
                'parameters': {
                    'size': size,
                    'n': n,
                    'prompt_extend': prompt_extend,
                    'watermark': watermark
                }
            }
            
            # 添加反向提示词
            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt
            
            print(f"[DEBUG] Creating wan2.6-t2i task: size={size}, n={n}, prompt_extend={prompt_extend}, watermark={watermark}")
            print(f"[DEBUG] Request params: {params}")
            
            # 使用multimodal-generation API（同步接口，不添加X-DashScope-Async头）
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # wan2.6-t2i同步接口，超时时间设置更长
            response = self.session.post(url, json=params, headers=headers, timeout=180)
            
            print(f"[DEBUG] Response status: {response.status_code}")
            result = response.json()
            print(f"[DEBUG] Response body: {result}")
            
            if result.get('request_id'):
                print(f"[INFO] Request ID: {result['request_id']}")
            
            response.raise_for_status()
            
            # 同步接口直接返回结果
            if result.get('output') and result['output'].get('choices'):
                output = result['output']
                
                # 提取生成的图片URL
                image_urls = []
                for choice in output.get('choices', []):
                    message = choice.get('message', {})
                    content = message.get('content', [])
                    for item in content:
                        if isinstance(item, dict) and item.get('image'):
                            image_urls.append(item['image'])
                
                return {
                    'image_urls': image_urls,
                    'request_id': result.get('request_id'),
                    'usage': result.get('usage', {})
                }
            
            # 处理错误响应
            error_msg = result.get('message', '未知错误')
            error_code = result.get('code', 'UNKNOWN')
            print(f"[ERROR] 执行wan2.6-t2i API失败: code={error_code}, message={error_msg}, request_id={result.get('request_id')}")
            return None
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                request_id = error_detail.get('request_id', 'N/A')
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
                print(f"[ERROR] 执行wan2.6-t2i API失败: {error_msg}, request_id: {request_id}")
            except:
                print(f"[ERROR] 执行wan2.6-t2i API失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 执行wan2.6-t2i API失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_z_image_task(self, prompt: str, size: str, n: int,
                             negative_prompt: str, prompt_extend: bool,
                             watermark: bool, callback: Callable = None) -> Optional[Dict]:
        """创建z-image-turbo任务（模拟异步）
        
        z-image-turbo使用同步接口，但为了保持用户体验一致：
        1. 立即返回PENDING状态的任务信息
        2. 在后台线程中执行实际的API请求
        3. 完成后更新任务状态
        
        Args:
            prompt: 提示词
            size: 图片尺寸
            n: 生成数量（z-image-turbo固定为1）
            negative_prompt: 反向提示词（z-image-turbo不支持）
            prompt_extend: 是否启用智能改写
            watermark: 是否添加水印（z-image-turbo不支持）
            callback: 后台任务完成后的回调函数
            
        Returns:
            任务信息字典（PENDING状态）
        """
        import uuid
        
        # 生成唯一任务ID
        task_id = f"zimage_{uuid.uuid4().hex[:16]}"
        
        # 立即返回PENDING状态的任务信息
        task_info = {
            'task_id': task_id,
            'task_status': 'PENDING',
            'task_type': 't2i',
            'prompt': prompt,
            'model': 'z-image-turbo',
            'size': size,
            'n': 1,  # z-image-turbo固定生成1张图片
            'negative_prompt': negative_prompt,
            'prompt_extend': prompt_extend,
            'watermark': watermark,
            'create_time': datetime.now().isoformat()
        }
        
        # 在后台线程中执行实际的API调用
        def execute_task():
            try:
                print(f"[INFO] 后台执行z-image-turbo任务: {task_id}")
                result = self._execute_z_image_api(prompt, size, prompt_extend)
                
                if result:
                    # 更新任务状态
                    update_data = {
                        'task_status': 'SUCCEEDED',
                        'image_urls': result.get('image_urls', []),
                        'request_id': result.get('request_id'),
                        'usage': result.get('usage', {})
                    }
                    print(f"[INFO] z-image-turbo任务完成: {task_id}, {len(update_data['image_urls'])} 张图片")
                else:
                    update_data = {
                        'task_status': 'FAILED',
                        'message': '图片生成失败'
                    }
                    print(f"[ERROR] z-image-turbo任务失败: {task_id}")
                
                # 调用回调函数更新缓存
                if callback:
                    callback(task_id, update_data)
                    
            except Exception as e:
                print(f"[ERROR] z-image-turbo后台任务执行失败: {task_id}, {e}")
                import traceback
                traceback.print_exc()
                if callback:
                    callback(task_id, {
                        'task_status': 'FAILED',
                        'message': str(e)
                    })
        
        # 提交到后台线程池
        print(f"[DEBUG] 提交z-image-turbo后台任务: {task_id}")
        future = _background_executor.submit(execute_task)
        print(f"[DEBUG] 后台任务已提交: {task_id}, future={future}")
        
        return task_info
    
    def _execute_z_image_api(self, prompt: str, size: str, prompt_extend: bool, max_retries: int = 3) -> Optional[Dict]:
        """执行z-image-turbo API调用（同步，带限流重试）
        
        Args:
            prompt: 提示词
            size: 图片尺寸
            prompt_extend: 是否启用智能改写
            max_retries: 最大重试次数（默认3次）
            
        Returns:
            包含image_urls的结果字典
        """
        import time
        
        for attempt in range(max_retries):
            try:
                # 构建z-image-turbo的请求参数（使用messages格式）
                params = {
                    'model': 'z-image-turbo',
                    'input': {
                        'messages': [
                            {
                                'role': 'user',
                                'content': [
                                    {
                                        'text': prompt
                                    }
                                ]
                            }
                        ]
                    },
                    'parameters': {
                        'size': size,
                        'prompt_extend': prompt_extend
                    }
                }
                
                if attempt > 0:
                    print(f"[INFO] z-image-turbo API 重试第 {attempt + 1}/{max_retries} 次")
                
                print(f"[DEBUG] Creating z-image-turbo task: size={size}, prompt_extend={prompt_extend}")
                print(f"[DEBUG] Request params: {params}")
                
                # 使用multimodal-generation API（同步接口，不添加X-DashScope-Async头）
                url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                # z-image-turbo同步接口，超时时间设置为120秒
                response = self.session.post(url, json=params, headers=headers, timeout=120)
                
                print(f"[DEBUG] Response status: {response.status_code}")
                result = response.json()
                print(f"[DEBUG] Response body: {result}")
                
                if result.get('request_id'):
                    print(f"[INFO] Request ID: {result['request_id']}")
                
                # 检查是否为429限流错误
                if response.status_code == 429:
                    error_code = result.get('code', '')
                    error_msg = result.get('message', '限流错误')
                    
                    if attempt < max_retries - 1:
                        # 指数退避：2^attempt * 2 秒 (2s, 4s, 8s)
                        wait_time = (2 ** attempt) * 2
                        print(f"[WARN] API限流 (429): {error_msg}, {wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue  # 重试
                    else:
                        print(f"[ERROR] API限流 (429): 达到最大重试次数, 放弃")
                        return None
                
                response.raise_for_status()
                
                # 同步接口直接返回结果
                if result.get('output') and result['output'].get('choices'):
                    output = result['output']
                    
                    # 提取生成的图片URL
                    image_urls = []
                    for choice in output.get('choices', []):
                        message = choice.get('message', {})
                        content = message.get('content', [])
                        for item in content:
                            if isinstance(item, dict) and item.get('image'):
                                image_urls.append(item['image'])
                    
                    if attempt > 0:
                        print(f"[INFO] 重试成功！生成 {len(image_urls)} 张图片")
                    
                    return {
                        'image_urls': image_urls,
                        'request_id': result.get('request_id'),
                        'usage': result.get('usage', {})
                    }
                
                # 处理错误响应
                error_msg = result.get('message', '未知错误')
                error_code = result.get('code', 'UNKNOWN')
                print(f"[ERROR] 执行z-image-turbo API失败: code={error_code}, message={error_msg}, request_id={result.get('request_id')}")
                return None
                
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP错误: {e.response.status_code}"
                try:
                    error_detail = e.response.json()
                    request_id = error_detail.get('request_id', 'N/A')
                    if error_detail.get('message'):
                        error_msg = f"{error_msg} - {error_detail['message']}"
                    
                    # 429错误特殊处理
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2
                        print(f"[WARN] {error_msg}, {wait_time}秒后重试... (request_id: {request_id})")
                        time.sleep(wait_time)
                        continue  # 重试
                    
                    print(f"[ERROR] 执行z-image-turbo API失败: {error_msg}, request_id: {request_id}")
                except:
                    print(f"[ERROR] 执行z-image-turbo API失败: {error_msg}")
                
                if attempt >= max_retries - 1:
                    return None
                    
            except Exception as e:
                print(f"[ERROR] 执行z-image-turbo API失败: {e}")
                if attempt >= max_retries - 1:
                    import traceback
                    traceback.print_exc()
                    return None
                else:
                    # 其他错误也重试
                    wait_time = (2 ** attempt) * 2
                    print(f"[WARN] API调用失败, {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
        
        return None

    def create_i2i_task(self, image_paths: List[str], prompt: str,
                        model: str = 'wan2.5-i2i-preview',
                        size: str = None, n: int = 1,
                        prompt_extend: bool = True,
                        negative_prompt: str = '',
                        callback: Callable = None) -> Optional[Dict]:
        """创建图生图任务

        Args:
            image_paths: 参考图片路径列表（最多3张）
            prompt: 提示词
            model: 模型名称
            size: 图片尺寸（qwen-image-edit-plus模型不支持，传None）
            n: 生成数量
            prompt_extend: 是否启用智能改写
            negative_prompt: 反向提示词
            callback: 后台任务完成后的回调函数（仅qwen-image-edit-plus使用）

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # qwen-image-edit-plus 使用不同的API和请求格式
            # 注意：qwen-image-edit-plus每次只生成1张图片，多图通过batch_count循环实现
            if model == 'qwen-image-edit-plus':
                return self._create_qwen_image_edit_task(image_paths, prompt, prompt_extend, negative_prompt, callback)
            
            # wan2.6-image 使用新的API格式
            if model == 'wan2.6-image':
                # 从callback参数中提取enable_interleave和max_images（通过特殊字典传递）
                enable_interleave = False
                max_images = 5
                if isinstance(callback, dict):
                    enable_interleave = callback.get('enable_interleave', False)
                    max_images = callback.get('max_images', 5)
                    callback = None
                return self._create_wan26_image_task(image_paths, prompt, size, n, prompt_extend, 
                                                     negative_prompt, enable_interleave, max_images)
            
            # wan2.5-i2i-preview 使用原有的API
            return self._create_wan_i2i_task(image_paths, prompt, model, size, n, prompt_extend, negative_prompt)
            
        except Exception as e:
            print(f"[ERROR] 创建图生图任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_qwen_image_edit_task(self, image_paths: List[str], prompt: str,
                                      prompt_extend: bool = True,
                                      negative_prompt: str = '',
                                      callback: Callable = None) -> Optional[Dict]:
        """创建 qwen-image-edit-plus 任务（后台异步执行，每次生成1张图片）"""
        import uuid
        
        # 生成临时任务ID
        task_id = f"qwen_{uuid.uuid4().hex[:16]}"
        
        # 立即返回PENDING状态的任务信息
        task_info = {
            'task_id': task_id,
            'task_status': 'PENDING',
            'task_type': 'i2i',
            'prompt': prompt,
            'model': 'qwen-image-edit-plus',
            'size': '保持原图比例',
            'n': 1,  # 固定为1，多图通过batch_count循环实现
            'prompt_extend': prompt_extend,
            'negative_prompt': negative_prompt,
            'create_time': datetime.now().isoformat()
        }
        
        # 在后台线程中执行实际的API调用
        def execute_task():
            try:
                print(f"[INFO] 后台执行qwen-image-edit-plus任务: {task_id}")
                result = self._execute_qwen_image_edit_api(image_paths, prompt, prompt_extend, negative_prompt)
                
                if result:
                    # 更新任务状态
                    update_data = {
                        'task_status': 'SUCCEEDED',
                        'results': result.get('results', []),
                        'request_id': result.get('request_id')
                    }
                    print(f"[INFO] qwen-image-edit-plus任务完成: {task_id}, {len(update_data['results'])} 张图片")
                else:
                    update_data = {
                        'task_status': 'FAILED',
                        'message': '图片生成失败'
                    }
                    print(f"[ERROR] qwen-image-edit-plus任务失败: {task_id}")
                
                # 调用回调函数更新缓存
                if callback:
                    callback(task_id, update_data)
                    
            except Exception as e:
                print(f"[ERROR] 后台任务执行失败: {task_id}, {e}")
                if callback:
                    callback(task_id, {
                        'task_status': 'FAILED',
                        'message': str(e)
                    })
        
        # 提交到后台线程池
        _background_executor.submit(execute_task)
        
        return task_info
    
    def _execute_qwen_image_edit_api(self, image_paths: List[str], prompt: str,
                                      prompt_extend: bool = True,
                                      negative_prompt: str = '') -> Optional[Dict]:
        """执行 qwen-image-edit-plus API调用（同步，每次生成1张图片）"""
        try:
            # 只使用第一张图片
            image_base64 = self.encode_image_to_base64(image_paths[0])
            
            # 构建 messages 格式的请求
            # 注意：始终使用 n=1，多图通过循环创建多个任务实现
            params = {
                'model': 'qwen-image-edit-plus',
                'input': {
                    'messages': [
                        {
                            'role': 'user',
                            'content': [
                                {'image': image_base64},
                                {'text': prompt}
                            ]
                        }
                    ]
                },
                'parameters': {
                    'n': 1,  # 固定为1，多图通过batch_count循环实现
                    'prompt_extend': prompt_extend,
                    'watermark': False
                }
            }
            
            # 添加反向提示词
            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt
            
            print(f"[DEBUG] Creating qwen-image-edit-plus task: n=1, negative_prompt={bool(negative_prompt)}")
            
            # 使用 multimodal-generation API（不支持异步调用）
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = self.session.post(url, json=params, headers=headers, timeout=120)
            
            print(f"[DEBUG] Response status: {response.status_code}")
            
            # 检查响应内容类型，避免解析非JSON响应
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                print(f"[ERROR] 非JSON响应: Content-Type={content_type}")
                print(f"[ERROR] 响应内容: {response.text[:500]}")
                return None
            
            try:
                result = response.json()
            except Exception as json_err:
                print(f"[ERROR] JSON解析失败: {json_err}")
                print(f"[ERROR] 响应内容: {response.text[:500]}")
                return None
            
            print(f"[DEBUG] Response body: {result}")
            
            if result.get('request_id'):
                print(f"[INFO] Request ID: {result['request_id']}")
            
            response.raise_for_status()
            
            # 同步调用直接返回结果，不返回task_id
            if result.get('output'):
                output = result['output']
                # 提取生成的图片URL
                image_urls = []
                if output.get('choices'):
                    for choice in output['choices']:
                        message = choice.get('message', {})
                        content = message.get('content', [])
                        for item in content:
                            if isinstance(item, dict) and item.get('image'):
                                image_urls.append(item['image'])
                
                # 构造一个与异步任务兼容的任务信息，状态直接设为SUCCEEDED
                task_info = {
                    'task_id': result.get('request_id', f"sync_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
                    'task_status': 'SUCCEEDED',
                    'task_type': 'i2i',
                    'prompt': prompt,
                    'model': 'qwen-image-edit-plus',
                    'size': '保持原图比例',
                    'n': 1,  # 固定为1
                    'prompt_extend': prompt_extend,
                    'request_id': result.get('request_id'),
                    'create_time': datetime.now().isoformat(),
                    'results': image_urls  # 直接包含结果URL
                }
                print(f"[INFO] qwen-image-edit-plus task completed: {len(image_urls)} images generated")
                return task_info
            
            error_msg = result.get('message', '未知错误')
            error_code = result.get('code', 'UNKNOWN')
            print(f"[ERROR] 创建qwen-image-edit-plus任务失败: code={error_code}, message={error_msg}")
            return None
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                # 检查响应是否为JSON格式
                content_type = e.response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    error_detail = e.response.json()
                    if error_detail.get('message'):
                        error_msg = f"{error_msg} - {error_detail['message']}"
                else:
                    # 非JSON响应，记录前500字符
                    error_msg = f"{error_msg} - 响应为非JSON格式: {e.response.text[:500]}"
                print(f"[ERROR] 创建qwen-image-edit-plus任务失败: {error_msg}")
            except Exception as parse_err:
                print(f"[ERROR] 创建qwen-image-edit-plus任务失败: {error_msg}, 解析异常: {parse_err}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建qwen-image-edit-plus任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_wan_i2i_task(self, image_paths: List[str], prompt: str,
                             model: str, size: str, n: int,
                             prompt_extend: bool,
                             negative_prompt: str = '') -> Optional[Dict]:
        """创建 wan2.5-i2i-preview 任务"""
        try:
            # 将所有图片编码为Base64
            image_base64_list = []
            for image_path in image_paths[:3]:  # 最多3张
                image_base64 = self.encode_image_to_base64(image_path)
                image_base64_list.append(image_base64)

            params = {
                'model': model,
                'input': {
                    'prompt': prompt,
                    'images': image_base64_list
                },
                'parameters': {
                    'prompt_extend': prompt_extend,
                    'n': n
                }
            }
            
            # 只有在指定size时才添加该参数
            if size:
                params['parameters']['size'] = size
            
            # 添加反向提示词
            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt

            print(f"[DEBUG] Creating i2i task: model={model}, size={size}, n={n}, negative_prompt={bool(negative_prompt)}")

            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/image2image/image-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)

            print(f"[DEBUG] Response status: {response.status_code}")
            result = response.json()
            print(f"[DEBUG] Response body: {result}")

            if result.get('request_id'):
                print(f"[INFO] Request ID: {result['request_id']}")

            response.raise_for_status()

            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 'i2i',
                    'prompt': prompt,
                    'model': model,
                    'size': size if size else '保持原图比例',
                    'n': n,
                    'prompt_extend': prompt_extend,
                    'negative_prompt': negative_prompt,
                    'request_id': result.get('request_id'),
                    'create_time': datetime.now().isoformat()
                }
                print(
                    f"[INFO] I2I task created successfully: {task_info['task_id']}, request_id: {task_info.get('request_id')}")
                return task_info

            error_msg = result.get('message', '未知错误')
            error_code = result.get('code', 'UNKNOWN')
            print(
                f"[ERROR] 创建图生图任务失败: code={error_code}, message={error_msg}, request_id={result.get('request_id')}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                request_id = error_detail.get('request_id', 'N/A')
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
                print(f"[ERROR] 创建图生图任务失败: {error_msg}, request_id: {request_id}")
            except:
                print(f"[ERROR] 创建图生图任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建图生图任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def create_t2v_task(self, prompt: str, model: str = 'wan2.6-t2v',
                        resolution: str = '720P', duration: int = 5,
                        audio: bool = False, audio_url: str = '',
                        negative_prompt: str = '', shot_type: str = 'single') -> Optional[Dict]:
        """创建文生视频任务

        Args:
            prompt: 提示词
            model: 模型名称 (wan2.6-t2v, wan2.5-t2v-preview, wan2.2-t2v-plus, wanx2.1-t2v-turbo, wanx2.1-t2v-plus)
            resolution: 分辨率 (480P, 720P, 1080P)
            duration: 视频时长（秒）(5, 10, 15)
            audio: 是否启用自动配音（wan2.5及以上支持）
            audio_url: 音频URL（自定义音频，wan2.5及以上支持）
            negative_prompt: 反向提示词
            shot_type: 镜头类型（single单镜头, multi多镜头，仅wan2.6支持）

        Returns:
            任务信息字典，包含task_id等字段
        """
        try:
            # 构建请求参数
            params = {
                'model': model,
                'input': {
                    'prompt': prompt
                },
                'parameters': {}
            }

            # 分辨率转换映射
            size_map = {
                '480P': '832*480',
                '720P': '1280*720',
                '1080P': '1920*1080'
            }
            
            # 添加分辨率参数
            if resolution:
                params['parameters']['size'] = size_map.get(resolution, '1280*720')

            # 添加时长参数
            if duration:
                params['parameters']['duration'] = duration

            # 添加反向提示词
            if negative_prompt:
                params['input']['negative_prompt'] = negative_prompt

            # 镜头类型（仅wan2.6支持multi多镜头）
            if shot_type and model == 'wan2.6-t2v':
                params['parameters']['shot_type'] = shot_type

            # 音频处理（wan2.5及以上版本支持）
            if model in ['wan2.6-t2v', 'wan2.5-t2v-preview']:
                if audio_url:
                    # 自定义音频URL放在input中
                    params['input']['audio_url'] = audio_url
                else:
                    # 自动配音开关
                    params['parameters']['audio'] = audio

            # 调试日志
            print(f"[DEBUG] Creating t2v task: model={model}, size={params['parameters'].get('size')}, duration={duration}, audio={audio}, shot_type={shot_type if model == 'wan2.6-t2v' else 'N/A'}")

            # 调用API - 文生视频使用video-generation接口
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/video-generation/video-synthesis"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            }

            response = self.session.post(url, json=params, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            # 提取任务信息
            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 't2v',
                    'prompt': prompt,
                    'model': model,
                    'resolution': resolution,
                    'duration': duration,
                    'audio': audio,
                    'audio_url': audio_url,
                    'negative_prompt': negative_prompt,
                    'shot_type': shot_type,
                    'request_id': result.get('request_id'),
                    'create_time': datetime.now().isoformat()
                }
                return task_info

            # 如果API返回了错误信息
            error_msg = result.get('message', '未知错误')
            print(f"[ERROR] 创建文生视频任务失败: {error_msg}")
            return None

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
            except:
                pass
            print(f"[ERROR] 创建文生视频任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建文生视频任务失败: {e}")
            return None

    def _create_wan26_image_task(self, image_paths: List[str], prompt: str, 
                                 size: str, n: int,
                                 prompt_extend: bool, negative_prompt: str,
                                 enable_interleave: bool = False,
                                 max_images: int = 5) -> Optional[Dict]:
        """创建wan2.6-image任务（异步接口）
        
        wan2.6-image支持两种模式：
        1. 图像编辑模式（enable_interleave=false）：支持多图输入（1-3张），参考图片生成
        2. 图文混合输出模式（enable_interleave=true）：支持0-1张图像，可生成图文混排内容
        3. 支持自定义分辨率：总像素在[768*768, 1280*1280]之间，宽高比[1:4, 4:1]
        
        Args:
            image_paths: 图片路径列表（图像编辑模式1-3张，图文混排模式0-1张）
            prompt: 提示词
            size: 图片尺寸
            n: 生成数量（图像编辑模式固定为1，图文混排模式通过max_images控制）
            prompt_extend: 是否启用智能改写（仅图像编辑模式生效）
            negative_prompt: 反向提示词
            enable_interleave: 是否启用图文混排模式
            max_images: 图文混排模式下最多生成的图像数量（1-5）
            
        Returns:
            任务信息字典
        """
        try:
            # 将所有图片编码为Base64
            image_base64_list = []
            if image_paths:
                # 图文混排模式：最多1张图；图像编辑模式：最多3张
                max_images_count = 1 if enable_interleave else 3
                for image_path in image_paths[:max_images_count]:
                    image_base64 = self.encode_image_to_base64(image_path)
                    image_base64_list.append(image_base64)
            
            # 构建wan2.6-image的请求参数（使用messages格式）
            content = [{'text': prompt}]
            
            # 添加图片到content数组中
            for image_base64 in image_base64_list:
                content.append({'image': image_base64})
            
            params = {
                'model': 'wan2.6-image',
                'input': {
                    'messages': [
                        {
                            'role': 'user',
                            'content': content
                        }
                    ]
                },
                'parameters': {
                    'watermark': False,
                    'n': 1,  # 固定为1，实际生成数量由enable_interleave和max_images控制
                    'enable_interleave': enable_interleave
                }
            }
            
            # 图像编辑模式才支持prompt_extend
            if not enable_interleave:
                params['parameters']['prompt_extend'] = prompt_extend
            
            # 图文混排模式设置max_images参数
            if enable_interleave:
                params['parameters']['max_images'] = max_images
            
            # 只有在指定size时才添加该参数
            if size:
                params['parameters']['size'] = size
            
            # 添加反向提示词
            if negative_prompt:
                params['parameters']['negative_prompt'] = negative_prompt
            
            mode = '图文混排' if enable_interleave else '图像编辑'
            print(f"[DEBUG] Creating wan2.6-image task: mode={mode}, size={size}, n=1, images={len(image_base64_list)}, enable_interleave={enable_interleave}, max_images={max_images if enable_interleave else 'N/A'}, negative_prompt={bool(negative_prompt)}")
            
            # 使用 image-generation API（异步调用）
            url = f"{Config.DASHSCOPE_BASE_URL}/services/aigc/image-generation/generation"
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable'
            }
            
            response = self.session.post(url, json=params, headers=headers, timeout=30)
            
            print(f"[DEBUG] Response status: {response.status_code}")
            result = response.json()
            print(f"[DEBUG] Response body: {result}")
            
            if result.get('request_id'):
                print(f"[INFO] Request ID: {result['request_id']}")
            
            response.raise_for_status()
            
            # 异步调用返回task_id
            if result.get('output') and result['output'].get('task_id'):
                task_info = {
                    'task_id': result['output']['task_id'],
                    'task_status': result['output'].get('task_status', 'PENDING'),
                    'task_type': 'i2i',
                    'prompt': prompt,
                    'model': 'wan2.6-image',
                    'size': size if size else '保持原图比例',
                    'n': 1,  # wan2.6-image每次只生成1张
                    'prompt_extend': prompt_extend if not enable_interleave else False,
                    'negative_prompt': negative_prompt,
                    'enable_interleave': enable_interleave,
                    'max_images': max_images if enable_interleave else None,
                    'request_id': result.get('request_id'),
                    'create_time': datetime.now().isoformat()
                }
                print(f"[INFO] wan2.6-image task created successfully: {task_info['task_id']}, request_id: {task_info.get('request_id')}")
                return task_info
            
            error_msg = result.get('message', '未知错误')
            error_code = result.get('code', 'UNKNOWN')
            print(f"[ERROR] 创建wan2.6-image任务失败: code={error_code}, message={error_msg}, request_id={result.get('request_id')}")
            return None
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                request_id = error_detail.get('request_id', 'N/A')
                if error_detail.get('message'):
                    error_msg = f"{error_msg} - {error_detail['message']}"
                print(f"[ERROR] 创建wan2.6-image任务失败: {error_msg}, request_id: {request_id}")
            except:
                print(f"[ERROR] 创建wan2.6-image任务失败: {error_msg}")
            return None
        except Exception as e:
            print(f"[ERROR] 创建wan2.6-image任务失败: {e}")
            import traceback
            traceback.print_exc()
            return None
