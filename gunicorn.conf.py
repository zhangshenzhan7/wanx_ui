"""
Gunicorn配置文件
生产环境WSGI服务器配置
"""
import multiprocessing
import os

# 服务器绑定地址和端口
bind = os.getenv('HOST', '0.0.0.0') + ':' + os.getenv('PORT', '8000')

# Worker进程配置
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gevent')
worker_connections = int(os.getenv('GUNICORN_WORKER_CONNECTIONS', 1000))

# 超时配置
timeout = int(os.getenv('GUNICORN_TIMEOUT', 30))
graceful_timeout = 30
keepalive = 5

# 进程管理
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = '-'  # 输出到stdout
errorlog = '-'   # 输出到stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = 'wanx-video-ui'

# 预加载应用
preload_app = False

# Daemon模式(生产环境可启用)
daemon = False

# PID文件
pidfile = None

# 临时文件目录
worker_tmp_dir = '/dev/shm' if os.path.exists('/dev/shm') else None

# Increase timeout for large file uploads
timeout = 120
