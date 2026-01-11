#!/bin/bash
###############################################################################
# 通义万相图生视频UI系统 - 服务器部署脚本 (通用隔离版)
# 适用于 Ubuntu/Debian 环境
# 核心改进：自动创建隔离环境(venv)，彻底解决系统包冲突(blinker/distutils)问题
###############################################################################

set -e  # 遇到错误立即退出

# 获取脚本所在目录的绝对路径
BASE_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$BASE_DIR"

echo "=========================================="
echo "🚀 通义万相图生视频UI - 智能部署 (隔离环境版)"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  检测到root用户。虽然可以运行，但建议使用普通用户以提高安全性。${NC}"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

########################################
# 1. 安装系统级依赖
########################################
echo -e "${GREEN}[1/7] 检查系统基础依赖${NC}"

SUDO=""
if [ "$EUID" -ne 0 ]; then
    SUDO="sudo"
fi

# 检查并安装 python3, pip, venv, ffmpeg
echo "正在更新软件源并安装必要工具..."
# 这里的 python3-venv 是关键，用于创建隔离环境
$SUDO apt update -qq || true
$SUDO apt install -y python3 python3-pip python3-venv python3-dev build-essential ffmpeg

# 验证安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 安装失败${NC}"
    exit 1
fi

echo "✅ 系统依赖安装完成"
echo ""

########################################
# 2. 创建并配置隔离环境 (Venv)
########################################
echo -e "${GREEN}[2/7] 配置独立运行环境 (Venv)${NC}"

VENV_DIR="$BASE_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "正在创建隔离环境..."
    python3 -m venv "$VENV_DIR"
    echo "✅ 隔离环境创建成功: $VENV_DIR"
else
    echo "✅ 检测到已存在隔离环境，跳过创建"
fi

# === 关键：将后续操作的 Python 和 Pip 指向隔离环境 ===
PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

echo "当前使用 Python: $PYTHON"
echo "当前使用 Pip: $PIP"
echo ""

########################################
# 3. 安装项目依赖
########################################
echo -e "${GREEN}[3/7] 安装项目依赖${NC}"

PIP_INDEX="http://mirrors.cloud.aliyuncs.com/pypi/simple/"
PIP_TRUST="-i $PIP_INDEX --trusted-host mirrors.cloud.aliyuncs.com"

echo "升级环境内 pip..."
"$PIP" install --upgrade pip $PIP_TRUST

echo "安装 requirements.txt..."
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ 未找到 requirements.txt${NC}"
    exit 1
fi

# 使用 --no-cache-dir 减小体积
"$PIP" install --no-cache-dir -r requirements.txt $PIP_TRUST

echo "验证依赖..."
"$PYTHON" -c "import flask, requests, gevent, gunicorn; print('✅ 核心依赖验证通过')" || {
    echo -e "${RED}❌ 依赖安装失败，请检查网络或报错信息${NC}"
    exit 1
}
echo ""

########################################
# 4. 配置环境变量
########################################
echo -e "${GREEN}[4/7] 配置环境变量${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ 已从模板创建 .env"

        # 生成随机密钥
        SECRET_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
        sed -i "s/FLASK_ENV=.*/FLASK_ENV=production/" .env
        echo "✅ 已自动生成安全密钥"
    else
        echo -e "${RED}❌ .env.example 不存在${NC}"
        exit 1
    fi
else
    echo "✅ .env 文件已存在"
fi
echo ""

########################################
# 5. 创建缓存目录
########################################
echo -e "${GREEN}[5/7] 初始化目录结构${NC}"

# 读取配置或使用默认值
CACHE_DIR=$(grep "^CACHE_DIR=" .env 2>/dev/null | cut -d'=' -f2 || echo "./cache")
CACHE_DIR=${CACHE_DIR:-./cache}

# 确保是绝对路径或相对于当前目录
mkdir -p "$CACHE_DIR/videos" "$CACHE_DIR/images" "$CACHE_DIR/tasks" "$CACHE_DIR/kf2v_tasks" "$CACHE_DIR/audios"
mkdir -p logs

echo "✅ 目录结构已就绪: $CACHE_DIR"
echo ""

########################################
# 6. 端口检查
########################################
echo -e "${GREEN}[6/7] 检查端口${NC}"

PORT=$(grep "^PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "6666")
PORT=${PORT:-6666}

if command -v lsof &> /dev/null; then
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  端口 $PORT 被占用${NC}"
        PID=$(lsof -t -i:$PORT)
        read -p "是否强制关闭占用进程 (PID: $PID)? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $PID 2>/dev/null || true
            echo "✅ 进程已清理"
        else
            echo "❌ 无法启动，端口被占用"
            exit 1
        fi
    fi
fi
echo ""

########################################
# 7. 启动服务
########################################
echo -e "${GREEN}[7/7] 启动管理${NC}"
echo ""
echo "请选择启动方式:"
echo "  1) 前台启动 (调试用)"
echo "  2) 后台启动 (nohup)"
echo "  3) 安装为系统服务 (开机自启)"
echo "  4) 退出"
echo ""
read -p "请输入选项 (1-4): " -n 1 -r choice
echo ""

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

case $choice in
    1)
        echo "正在启动..."
        "$PYTHON" -m gunicorn -c gunicorn.conf.py wsgi:app
        ;;
    2)
        echo "正在后台启动..."
        nohup "$PYTHON" -m gunicorn -c gunicorn.conf.py wsgi:app > logs/app.log 2>&1 &
        sleep 2
        echo "✅ 服务已在后台运行"
        echo "日志查看: tail -f logs/app.log"
        ;;
    3)
        echo "正在生成 systemd 服务文件..."
        SERVICE_FILE="/tmp/wanx-video.service"
        USER=$(whoami)

        # 注意：这里 ExecStart 直接指向了 venv 中的 gunicorn，确保环境正确
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=WanX Video UI Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BASE_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        echo "✅ 服务文件已生成"
        echo "请执行以下命令完成安装:"
        echo "  sudo cp $SERVICE_FILE /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable --now wanx-video"
        ;;
    *)
        echo "已退出"
        ;;
esac

echo ""
echo "✅ 部署脚本执行完毕"

