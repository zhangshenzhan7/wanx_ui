"""
Flask应用工厂
"""
from flask import Flask
import os


def create_app(config_name='default'):
    """
    创建Flask应用实例
    
    Args:
        config_name: 配置名称
        
    Returns:
        Flask应用实例
    """
    # 创建应用实例
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # 加载配置
    from config import Config
    app.config.from_object(Config)
    
    # 确保缓存目录存在
    os.makedirs(Config.CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(Config.CACHE_DIR, 'images'), exist_ok=True)
    os.makedirs(os.path.join(Config.CACHE_DIR, 'videos'), exist_ok=True)
    os.makedirs(os.path.join(Config.CACHE_DIR, 'tasks'), exist_ok=True)
    os.makedirs(os.path.join(Config.CACHE_DIR, 'kf2v_tasks'), exist_ok=True)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    return app


def register_blueprints(app):
    """注册蓝图"""
    # 注册健康检查蓝图
    try:
        from core.blueprints.health import health_bp
        app.register_blueprint(health_bp)
    except ImportError:
        pass
    
    # 后续逐步迁移到蓝图架构
    pass


def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found(error):
        from flask import jsonify
        return jsonify({'success': False, 'error': {'code': 'NOT_FOUND', 'message': '资源不存在'}}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        return jsonify({'success': False, 'error': {'code': 'INTERNAL_ERROR', 'message': '服务器内部错误'}}), 500


# 为了兼容性,直接导入原app.py的app实例
# 后续逐步迁移到新架构
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入原有app实例
try:
    from app_legacy import app
except ImportError:
    # 如果没有app_legacy.py,则创建新应用
    app = create_app()
