import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 服务器配置
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # ========== 缓存目录配置 ==========
    CACHE_DIR = os.getenv('CACHE_DIR', './cache')
    
    # 上传文件目录 (按任务类型分类)
    UPLOADS_DIR = os.path.join(CACHE_DIR, 'uploads')
    UPLOAD_I2V_DIR = os.path.join(UPLOADS_DIR, 'i2v')      # 图生视频上传图片
    UPLOAD_KF2V_DIR = os.path.join(UPLOADS_DIR, 'kf2v')    # 首尾帧上传图片
    UPLOAD_I2I_DIR = os.path.join(UPLOADS_DIR, 'i2i')      # 图生图参考图片
    UPLOAD_R2V_DIR = os.path.join(UPLOADS_DIR, 'r2v')      # 参考生视频上传视频
    UPLOAD_AUDIO_DIR = os.path.join(UPLOADS_DIR, 'audios') # 音频文件
    UPLOAD_VOICE_DIR = os.path.join(UPLOADS_DIR, 'voice')  # 语音复刻样本
    
    # 资产库目录
    ASSETS_DIR = os.path.join(CACHE_DIR, 'assets')
    ASSETS_STORYBOARD_DIR = os.path.join(ASSETS_DIR, 'storyboard')  # 分镜库
    ASSETS_ARTWORK_DIR = os.path.join(ASSETS_DIR, 'artwork')        # 原画库
    ASSETS_VIDEO_DIR = os.path.join(ASSETS_DIR, 'video')            # 视频库
    
    # 输出文件目录 (按任务类型分类)
    OUTPUTS_DIR = os.path.join(CACHE_DIR, 'outputs')
    OUTPUT_I2V_DIR = os.path.join(OUTPUTS_DIR, 'i2v')      # 图生视频输出视频
    OUTPUT_KF2V_DIR = os.path.join(OUTPUTS_DIR, 'kf2v')    # 首尾帧输出视频
    OUTPUT_T2I_DIR = os.path.join(OUTPUTS_DIR, 't2i')      # 文生图输出图片
    OUTPUT_I2I_DIR = os.path.join(OUTPUTS_DIR, 'i2i')      # 图生图输出图片
    OUTPUT_R2V_DIR = os.path.join(OUTPUTS_DIR, 'r2v')      # 参考生视频输出视频
    OUTPUT_T2V_DIR = os.path.join(OUTPUTS_DIR, 't2v')      # 文生视频输出视频
    OUTPUT_VOICE_DIR = os.path.join(OUTPUTS_DIR, 'voice')  # 语音合成输出
    
    # 任务元数据目录 (按任务类型分类)
    TASKS_DIR = os.path.join(CACHE_DIR, 'tasks')
    TASK_I2V_DIR = os.path.join(TASKS_DIR, 'i2v')          # 图生视频任务
    TASK_KF2V_DIR = os.path.join(TASKS_DIR, 'kf2v')        # 首尾帧任务
    TASK_T2I_DIR = os.path.join(TASKS_DIR, 't2i')          # 文生图任务
    TASK_I2I_DIR = os.path.join(TASKS_DIR, 'i2i')          # 图生图任务
    TASK_R2V_DIR = os.path.join(TASKS_DIR, 'r2v')          # 参考生视频任务
    TASK_T2V_DIR = os.path.join(TASKS_DIR, 't2v')          # 文生视频任务
    TASK_VOICE_DIR = os.path.join(TASKS_DIR, 'voice')      # 语音复刻任务
    
    # 兼容旧配置 (deprecated, 后续移除)
    VIDEO_CACHE_DIR = OUTPUT_I2V_DIR
    IMAGE_CACHE_DIR = UPLOAD_I2V_DIR
    
    # 通义万相API配置
    DASHSCOPE_BASE_URL = 'https://dashscope.aliyuncs.com/api/v1'
    
    # 上传配置
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp', 'mp4', 'mov', 'avi', 'webm'}
    
    @staticmethod
    def init_app(app):
        """初始化应用，创建必要的目录结构"""
        # 创建上传目录
        os.makedirs(Config.UPLOAD_I2V_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_KF2V_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_I2I_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_R2V_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_AUDIO_DIR, exist_ok=True)
        os.makedirs(Config.UPLOAD_VOICE_DIR, exist_ok=True)
        
        # 创建输出目录
        os.makedirs(Config.OUTPUT_I2V_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_KF2V_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_T2I_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_I2I_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_R2V_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_T2V_DIR, exist_ok=True)
        os.makedirs(Config.OUTPUT_VOICE_DIR, exist_ok=True)
        
        # 创建任务目录
        os.makedirs(Config.TASK_I2V_DIR, exist_ok=True)
        os.makedirs(Config.TASK_KF2V_DIR, exist_ok=True)
        os.makedirs(Config.TASK_T2I_DIR, exist_ok=True)
        os.makedirs(Config.TASK_I2I_DIR, exist_ok=True)
        os.makedirs(Config.TASK_R2V_DIR, exist_ok=True)
        os.makedirs(Config.TASK_T2V_DIR, exist_ok=True)
        os.makedirs(Config.TASK_VOICE_DIR, exist_ok=True)
        
        # 创建资产库目录
        os.makedirs(Config.ASSETS_STORYBOARD_DIR, exist_ok=True)
        os.makedirs(Config.ASSETS_ARTWORK_DIR, exist_ok=True)
        os.makedirs(Config.ASSETS_VIDEO_DIR, exist_ok=True)
