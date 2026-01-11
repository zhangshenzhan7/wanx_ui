"""
WSGI入口文件
用于Gunicorn等生产级WSGI服务器启动应用
"""
from app import app

if __name__ == "__main__":
    app.run()
