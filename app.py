"""
Wanx UI - 视频/图像生成服务 Flask 应用

重构说明：
- 原始 app.py (3671行) 已备份为 app.py.backup
- 采用蓝图模式将路由拆分为11个模块
- 分层架构：路由层 -> 服务层 -> 底层服务
- 所有API接口保持向后兼容
"""

from flask import Flask
from config import Config

# 导入蓝图
from blueprints.auth import auth_bp
from blueprints.prompt import prompt_bp
from blueprints.media import media_bp
from blueprints.i2v import i2v_bp
from blueprints.t2v import t2v_bp
from blueprints.t2i import t2i_bp
from blueprints.i2i import i2i_bp
from blueprints.kf2v import kf2v_bp
from blueprints.r2v import r2v_bp
from blueprints.asset import asset_bp
from blueprints.project import project_bp
from blueprints.voice import voice_bp
# from core.blueprints.health import health_bp  # 可选：健康检查（需要安装psutil）


# 创建Flask应用
app = Flask(__name__)
app.config.from_object(Config)

# 初始化应用，创建必要的目录结构
Config.init_app(app)

# 注册蓝图
app.register_blueprint(auth_bp)

# 提示词优化
app.register_blueprint(prompt_bp)

# 媒体文件服务（图片、视频、音频）
app.register_blueprint(media_bp)

# 任务模块
app.register_blueprint(i2v_bp)    # 图生视频
app.register_blueprint(t2v_bp)    # 文生视频
app.register_blueprint(t2i_bp)    # 文生图
app.register_blueprint(i2i_bp)    # 图生图
app.register_blueprint(kf2v_bp)   # 首尾帧生视频
app.register_blueprint(r2v_bp)    # 参考生视频

# 资产库和项目管理
app.register_blueprint(asset_bp)
app.register_blueprint(project_bp)

# 语音复刻
app.register_blueprint(voice_bp)

# 健康检查（可选，需要安装psutil）
# app.register_blueprint(health_bp)




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
