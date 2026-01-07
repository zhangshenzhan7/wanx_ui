"""任务通用处理器"""
import uuid
from core.utils.validators import validate_batch_count


class TaskHandler:
    """任务通用处理器
    
    提取任务处理的通用逻辑，减少路由层代码重复
    """
    
    @staticmethod
    def extract_task_params(request_data, task_type):
        """提取任务参数
        
        从请求数据中提取通用参数，验证必需参数，设置默认值
        
        Args:
            request_data: 请求数据字典
            task_type: 任务类型（i2v, t2v, t2i, i2i, kf2v, r2v）
            
        Returns:
            task_params字典
        """
        params = {
            'prompt': request_data.get('prompt', '').strip(),
            'model': request_data.get('model'),
            'negative_prompt': request_data.get('negative_prompt', ''),
            'batch_count': validate_batch_count(request_data.get('batch_count', 1))
        }
        
        # 根据任务类型添加特定参数
        if task_type in ['i2v', 't2v', 'kf2v']:
            params['resolution'] = request_data.get('resolution', '720P')
            params['duration'] = int(request_data.get('duration', 5))
            params['audio'] = request_data.get('audio', False)
            params['audio_url'] = request_data.get('audio_url', '')
            params['watermark'] = request_data.get('watermark', False)
            
        if task_type in ['i2v', 'kf2v']:
            params['prompt_extend'] = request_data.get('prompt_extend', True)
            
        if task_type in ['t2i', 'i2i']:
            params['size'] = request_data.get('size', '1024*1024')
            params['n'] = request_data.get('n', 1)
            params['watermark'] = request_data.get('watermark', False)
            params['prompt_extend'] = request_data.get('prompt_extend', True)
            
        if task_type in ['t2v', 'r2v']:
            params['shot_type'] = request_data.get('shot_type', 'single')
            
        if task_type == 'r2v':
            params['seed'] = request_data.get('seed')
            
        return params
    
    @staticmethod
    def prepare_batch_info(batch_count):
        """准备批次信息
        
        生成batch_id，验证批次数量
        
        Args:
            batch_count: 批次数量
            
        Returns:
            (batch_id, validated_batch_count)
        """
        batch_count = validate_batch_count(batch_count)
        batch_id = str(uuid.uuid4()) if batch_count > 1 else None
        return batch_id, batch_count
    
    @staticmethod
    def build_task_response(tasks, batch_id=None):
        """构建任务响应
        
        Args:
            tasks: 任务列表
            batch_id: 批次ID
            
        Returns:
            响应数据字典
        """
        batch_count = len(tasks)
        message = f'成功创建{batch_count}个任务' if batch_count > 1 else '任务创建成功'
        
        response = {
            'success': True,
            'tasks': tasks,
            'message': message
        }
        
        if batch_id:
            response['batch_id'] = batch_id
            
        return response
    
    @staticmethod
    def add_task_urls(task, task_type, api_key_hash):
        """添加任务相关的URL信息
        
        Args:
            task: 任务字典
            task_type: 任务类型
            api_key_hash: API Key哈希
            
        Returns:
            更新后的任务字典
        """
        # 添加图片URL
        if task_type == 'i2v' and task.get('image_filename'):
            task['image_url'] = f'/api/image/i2v/{api_key_hash}/{task["image_filename"]}'
            
        # 添加视频URL
        if task.get('task_status') == 'SUCCEEDED':
            if task_type in ['i2v', 't2v', 'kf2v', 'r2v']:
                task['local_video_path'] = f'/api/video/{task_type}/{api_key_hash}/{task["task_id"]}.mp4'
            elif task_type == 't2i' and task.get('local_filenames'):
                task['local_image_urls'] = [f'/api/t2i-image/{api_key_hash}/{fn}' for fn in task['local_filenames']]
            elif task_type == 'i2i' and task.get('local_filenames'):
                task['local_image_urls'] = [f'/api/i2i-image/{api_key_hash}/{fn}' for fn in task['local_filenames']]
        
        return task
