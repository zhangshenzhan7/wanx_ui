"""
健康检查和监控接口

提供以下端点:
- /health: 基础健康检查(存活探针)
- /ready: 就绪检查(就绪探针)
- /status: 详细状态信息
- /metrics: Prometheus格式指标
"""

from flask import Blueprint, jsonify, current_app
from datetime import datetime
import os
import psutil
import time
from typing import Dict, Any

health_bp = Blueprint('health', __name__)

# 应用启动时间
_start_time = time.time()

# 简单的指标收集器
_metrics = {
    'requests_total': 0,
    'requests_by_status': {},
    'task_created': 0,
    'task_succeeded': 0,
    'task_failed': 0,
}


def increment_metric(metric_name: str, value: int = 1, labels: Dict[str, str] = None):
    """递增指标计数"""
    if metric_name in _metrics:
        if isinstance(_metrics[metric_name], dict) and labels:
            key = '_'.join(f"{k}:{v}" for k, v in labels.items())
            _metrics[metric_name][key] = _metrics[metric_name].get(key, 0) + value
        else:
            _metrics[metric_name] += value


@health_bp.route('/health', methods=['GET'])
def health_check():
    """基础健康检查(存活探针)
    
    检查应用进程是否存活
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """就绪检查(就绪探针)
    
    检查应用是否准备好接收流量
    """
    checks = {}
    all_ready = True
    
    # 检查缓存目录是否可写
    try:
        cache_dir = os.getenv('CACHE_DIR', './cache')
        test_file = os.path.join(cache_dir, '.health_check')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        checks['cache_dir'] = 'ok'
    except Exception as e:
        checks['cache_dir'] = f'error: {str(e)}'
        all_ready = False
    
    # 检查日志目录是否可写
    try:
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        test_file = os.path.join(log_dir, '.health_check')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        checks['log_dir'] = 'ok'
    except Exception as e:
        checks['log_dir'] = f'error: {str(e)}'
        all_ready = False
    
    status_code = 200 if all_ready else 503
    
    return jsonify({
        'status': 'ready' if all_ready else 'not_ready',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), status_code


@health_bp.route('/status', methods=['GET'])
def status_check():
    """详细状态信息
    
    返回应用运行状态、资源使用情况等
    """
    # 计算运行时长
    uptime_seconds = time.time() - _start_time
    uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"
    
    # 获取进程资源使用情况
    process = psutil.Process()
    
    # 获取系统资源使用情况
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('.')
    
    return jsonify({
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'uptime': uptime_str,
        'uptime_seconds': int(uptime_seconds),
        'process': {
            'pid': process.pid,
            'cpu_percent': process.cpu_percent(),
            'memory_mb': round(process.memory_info().rss / 1024 / 1024, 2),
            'threads': process.num_threads(),
        },
        'system': {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_mb': round(memory.available / 1024 / 1024, 2),
            'disk_percent': disk.percent,
            'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 2),
        },
        'metrics': {
            'requests_total': _metrics.get('requests_total', 0),
            'task_created': _metrics.get('task_created', 0),
            'task_succeeded': _metrics.get('task_succeeded', 0),
            'task_failed': _metrics.get('task_failed', 0),
        }
    })


@health_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus格式指标
    
    暴露应用指标供Prometheus采集
    """
    lines = []
    
    # 请求总数
    lines.append('# HELP wanx_requests_total Total number of HTTP requests')
    lines.append('# TYPE wanx_requests_total counter')
    lines.append(f'wanx_requests_total {_metrics.get("requests_total", 0)}')
    
    # 按状态码分组的请求数
    lines.append('# HELP wanx_requests_by_status HTTP requests by status code')
    lines.append('# TYPE wanx_requests_by_status counter')
    for label, count in _metrics.get('requests_by_status', {}).items():
        status_code = label.split(':')[1]
        lines.append(f'wanx_requests_by_status{{status="{status_code}"}} {count}')
    
    # 任务指标
    lines.append('# HELP wanx_task_created Total number of tasks created')
    lines.append('# TYPE wanx_task_created counter')
    lines.append(f'wanx_task_created {_metrics.get("task_created", 0)}')
    
    lines.append('# HELP wanx_task_succeeded Total number of tasks succeeded')
    lines.append('# TYPE wanx_task_succeeded counter')
    lines.append(f'wanx_task_succeeded {_metrics.get("task_succeeded", 0)}')
    
    lines.append('# HELP wanx_task_failed Total number of tasks failed')
    lines.append('# TYPE wanx_task_failed counter')
    lines.append(f'wanx_task_failed {_metrics.get("task_failed", 0)}')
    
    # 运行时长
    uptime = time.time() - _start_time
    lines.append('# HELP wanx_uptime_seconds Application uptime in seconds')
    lines.append('# TYPE wanx_uptime_seconds gauge')
    lines.append(f'wanx_uptime_seconds {int(uptime)}')
    
    # 系统资源
    process = psutil.Process()
    lines.append('# HELP wanx_process_cpu_percent Process CPU usage percentage')
    lines.append('# TYPE wanx_process_cpu_percent gauge')
    lines.append(f'wanx_process_cpu_percent {process.cpu_percent()}')
    
    lines.append('# HELP wanx_process_memory_bytes Process memory usage in bytes')
    lines.append('# TYPE wanx_process_memory_bytes gauge')
    lines.append(f'wanx_process_memory_bytes {process.memory_info().rss}')
    
    return '\n'.join(lines) + '\n', 200, {'Content-Type': 'text/plain; charset=utf-8'}
