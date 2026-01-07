"""
结构化日志工具模块

提供统一的日志记录接口,支持:
- 结构化JSON格式日志
- 按级别自动路由到不同处理器
- 上下文信息自动注入(request_id, user_hash等)
- 开发/生产环境自适应
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """结构化JSON日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # 添加上下文信息
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        # 添加额外字段
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # 添加异常堆栈
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # 添加位置信息(仅DEBUG级别)
        if record.levelno == logging.DEBUG:
            log_data['location'] = {
                'file': record.filename,
                'line': record.lineno,
                'function': record.funcName
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器(开发环境)"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志为彩色输出"""
        color = self.COLORS.get(record.levelname, '')
        
        # 基础信息
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level = f"{color}{record.levelname:8}{self.RESET}"
        logger_name = f"{record.name:30}"
        message = record.getMessage()
        
        # 构建输出
        output = f"{timestamp} | {level} | {logger_name} | {message}"
        
        # 添加上下文信息
        if hasattr(record, 'context') and record.context:
            context_str = ' '.join([f"{k}={v}" for k, v in record.context.items()])
            output += f" [{context_str}]"
        
        # 添加额外字段
        if hasattr(record, 'extra_data') and record.extra_data:
            extra_str = ' '.join([f"{k}={v}" for k, v in record.extra_data.items()])
            output += f" {{{extra_str}}}"
        
        # 添加异常堆栈
        if record.exc_info:
            output += '\n' + self.formatException(record.exc_info)
        
        return output


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """设置并返回日志器
    
    Args:
        name: 日志器名称(通常使用__name__)
        level: 日志级别(DEBUG/INFO/WARNING/ERROR/CRITICAL)
    
    Returns:
        配置好的日志器实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    # 从环境变量获取配置
    env = os.getenv('FLASK_ENV', 'development')
    log_level = level or os.getenv('LOG_LEVEL', 'DEBUG' if env == 'development' else 'INFO')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 开发环境:彩色控制台输出
    if env == 'development':
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)
    
    # 生产环境:JSON文件输出
    else:
        # 确保日志目录存在
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # 普通日志文件
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=30,  # 保留30个文件
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        
        # 错误日志单独文件
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'error.log',
            maxBytes=100 * 1024 * 1024,
            backupCount=30,
            encoding='utf-8'
        )
        error_handler.setFormatter(StructuredFormatter())
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)
        
        # 控制台也输出ERROR级别
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(StructuredFormatter())
        console_handler.setLevel(logging.ERROR)
        logger.addHandler(console_handler)
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str,
                    context: Optional[Dict[str, Any]] = None,
                    extra: Optional[Dict[str, Any]] = None,
                    exc_info: bool = False):
    """带上下文的日志记录
    
    Args:
        logger: 日志器实例
        level: 日志级别
        message: 日志消息
        context: 上下文信息(user_hash, task_id等)
        extra: 额外字段(性能指标等)
        exc_info: 是否包含异常堆栈
    """
    # 创建日志记录
    log_record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        '(unknown file)', 0, message, (), None
    )
    
    # 添加上下文和额外字段
    if context:
        log_record.context = context
    if extra:
        log_record.extra_data = extra
    
    # 处理日志
    logger.handle(log_record)


# 预配置的日志器
app_logger = setup_logger('app')
service_logger = setup_logger('app.services')
api_logger = setup_logger('app.api')


# 便捷函数
def log_api_request(method: str, path: str, status_code: int,
                   duration_ms: float, user_hash: Optional[str] = None):
    """记录API请求日志"""
    log_with_context(
        api_logger, 'INFO',
        f'{method} {path} {status_code}',
        context={'user_hash': user_hash} if user_hash else {},
        extra={'duration_ms': duration_ms}
    )


def log_task_event(event: str, task_id: str, user_hash: str, **kwargs):
    """记录任务事件日志"""
    log_with_context(
        service_logger, 'INFO',
        f'Task event: {event}',
        context={'task_id': task_id, 'user_hash': user_hash},
        extra=kwargs
    )


def log_error(message: str, error: Exception, context: Optional[Dict] = None):
    """记录错误日志"""
    log_with_context(
        app_logger, 'ERROR',
        message,
        context=context or {},
        exc_info=True
    )
