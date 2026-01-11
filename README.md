# 通义万相 Web UI

通义万相（WanX）Web UI 是一个基于 Flask 的 Web 应用程序，提供了通义万相 AI 图像和视频生成能力的可视化界面。支持文生图、图生图、文生视频、图生视频、参考生视频等多种 AIGC 功能。

## ✨ 主要功能
<video src="static/demo_360p_4mb.mp4" width="360" controls autoplay loop muted playsinline></video>


### 图像生成
- **文生图（Text-to-Image）**
  - 支持 wan2.6-t2i、wan2.5-t2i-preview 等多个模型
  - 同步/异步调用模式
  - 支持自定义分辨率（1024×1024、720×1280、1280×720）
  - 批量生成
  - 提示词扩展和反向提示词支持
  - 水印控制

- **图生图（Image-to-Image）**
  - 支持 wan2.5-i2i-preview 等模型
  - 支持多图参考
  - 保持原图比例或自定义分辨率
  - 批量生成

### 视频生成
- **文生视频（Text-to-Video）**
  - 支持 5 款模型：
    - wan2.6-t2v：有声视频 + 多镜头叙事，720P/1080P，5/10/15秒
    - wan2.5-t2v-preview：有声视频，480P/720P/1080P，5/10秒
    - wan2.2-t2v-plus：专业版，480P/1080P，5秒
    - wanx2.1-t2v-turbo：极速版，480P/720P，5秒
    - wanx2.1-t2v-plus：专业版，720P，5秒
  - 支持自动配音或自定义音频
  - 多镜头叙事（wan2.6）

- **图生视频（Image-to-Video）**
  - 支持 wan2.6-i2v 模型
  - 输出分辨率：720P/1080P
  - 视频时长：5/10/15秒
  - 支持自动配音或自定义音频
  - 视频特效配置

- **参考生视频（Reference-to-Video）**
  - 支持 wan2.6-r2v 模型
  - 基于参考视频生成多镜头有声视频
  - 支持 720P/1080P 分辨率
  - 输出时长：5/10秒
  - 30fps MP4 格式

### 语音复刻（CosyVoice）
- **语音复刻**
  - 基于阿里云 CosyVoice（cosyvoice-v3-plus 模型）
  - 上传 5-30 秒语音样本创建自定义音色
  - 支持 WAV、MP3 格式
  - 音色处理时间约 1-3 分钟

- **语音合成**
  - 系统音色：阳光大男孩、欢脱元气女
  - 自定义音色：使用复刻的个人音色
  - 合成参数调节：音量（0-100）、语速（0.5-2.0）、音高（0.5-2.0）
  - 文本长度限制：1000 字符
  - 输出格式：MP3

### 核心特性
- 🔐 **API Key 隔离**：每个用户独立的工作空间和缓存
- 💾 **本地缓存**：自动缓存生成的图片和视频
- 📜 **任务历史**：完整的任务历史记录和管理
- 🎨 **响应式设计**：支持拖拽上传、实时预览
- 🔄 **任务管理**：任务状态实时查询、重新生成
- 📁 **素材管理**：与 assets 模块联动，便于素材管理

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd wanx_ui
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，设置必要的配置项
```

必要的配置项：
- `SECRET_KEY`: Flask 会话密钥
- `FLASK_ENV`: 运行环境（development/production）
- `HOST`: 服务器地址（默认 0.0.0.0）
- `PORT`: 服务器端口（默认 8000）

4. **运行应用**

开发环境：
```bash
python app.py
```

生产环境（使用 Gunicorn）：
```bash
./run.sh
# 或
gunicorn -c gunicorn.conf.py wsgi:app
```

5. **访问应用**

打开浏览器访问：`http://localhost:8000`

## 📁 项目结构

```
wanx_ui/
├── app.py                      # Flask 应用主文件
├── config.py                   # 配置文件
├── wsgi.py                     # WSGI 入口
├── gunicorn.conf.py           # Gunicorn 配置
├── requirements.txt           # Python 依赖
├── run.sh                     # 启动脚本
│
├── services/                  # 业务逻辑服务
│   ├── video_service.py      # 视频/图像生成服务
│   ├── cache_service.py      # 缓存管理服务
│   └── audio_service.py      # 音频处理服务
│
├── app/                       # 应用模块
│   ├── blueprints/           # Flask 蓝图
│   │   └── health.py         # 健康检查
│   ├── services/             # 应用服务
│   │   └── storage_service.py # 存储服务
│   └── utils/                # 工具函数
│       ├── logger.py         # 日志工具
│       └── response.py       # 响应工具
│
├── templates/                 # HTML 模板
│   ├── index.html            # 首页（API Key 输入）
│   ├── workspace.html        # 工作区（图生视频）
│   ├── text2image.html       # 文生图
│   ├── image2image.html      # 图生图
│   ├── text2video.html       # 文生视频
│   ├── reference2video.html  # 参考生视频
│   ├── kf2v.html             # 关键帧生视频
│   ├── assets.html           # 素材管理
│   └── base.html             # 基础模板
│
├── static/                    # 静态资源
│   ├── common.css            # 通用样式
│   ├── common.js             # 通用脚本
│   ├── asset-picker.js       # 素材选择器
│   ├── batch-video.js        # 批量视频处理
│   └── image-cropper.js      # 图片裁剪
│
├── config/                    # 配置文件
│   └── video_effects.json    # 视频特效配置
│
├── scripts/                   # 工具脚本
│   ├── generate_posters.py   # 生成海报
│   └── migrate_cache.py      # 缓存迁移
│
└── models/                    # 数据模型
    └── user.py               # 用户模型
```

## 🔧 配置说明

### 环境变量配置（.env）

#### Flask 配置
- `SECRET_KEY`: Flask 会话加密密钥（必须）
- `FLASK_ENV`: 运行环境（development/production）

#### 服务器配置
- `HOST`: 监听地址（默认 0.0.0.0）
- `PORT`: 监听端口（默认 8000）

#### Gunicorn 配置
- `GUNICORN_WORKERS`: 工作进程数（默认 5）
- `GUNICORN_WORKER_CLASS`: 工作模式（默认 gevent）
- `GUNICORN_WORKER_CONNECTIONS`: 每个工作进程的连接数（默认 1000）
- `GUNICORN_TIMEOUT`: 超时时间（默认 30 秒）

#### 缓存配置
- `CACHE_DIR`: 缓存根目录（默认 ./cache）
- `VIDEO_CACHE_DIR`: 视频缓存目录（默认 ./cache/videos）
- `IMAGE_CACHE_DIR`: 图片缓存目录（默认 ./cache/images）

#### 存储优化配置
- `STORAGE_SYNC_ENABLED`: 启用存储同步（默认 true）
- `STORAGE_SYNC_DELAY`: 同步延迟（默认 0.05 秒）
- `STORAGE_READ_RETRY`: 读取重试次数（默认 3）
- `STORAGE_LOCK_TIMEOUT`: 锁超时时间（默认 30 秒）
- `DIR_LIST_CACHE_TTL`: 目录列表缓存时间（默认 30 秒）

### 视频特效配置（config/video_effects.json）

包含各种视频生成的特效配置，用于图生视频等功能。

## 📝 使用说明

### 1. 首次使用

1. 访问首页，输入通义万相 API Key
2. 系统会验证 API Key 的有效性
3. 验证成功后自动跳转到工作区

### 2. 文生图

1. 点击导航栏的"文生图"
2. 输入提示词
3. 选择模型和参数（分辨率、生成数量等）
4. 点击"生成图片"
5. 等待生成完成，查看结果

### 3. 图生图

1. 点击导航栏的"图生图"
2. 上传参考图片（支持多图）
3. 输入提示词
4. 选择模型和参数
5. 点击"生成图片"

### 4. 文生视频

1. 点击导航栏的"文生视频"
2. 输入提示词
3. 选择模型、分辨率、时长等参数
4. 可选：上传自定义音频或启用自动配音
5. 点击"生成视频"
6. 等待生成完成（异步任务，可在任务历史中查看）

### 5. 图生视频

1. 在工作区页面上传参考图片
2. 输入提示词
3. 选择分辨率、时长、特效等参数
4. 可选：上传自定义音频
5. 点击"生成视频"
6. 查看任务进度和结果

### 6. 参考生视频

1. 点击导航栏的"参考生视频"
2. 上传参考视频文件
3. 输入提示词
4. 选择分辨率和时长
5. 点击"生成视频"
6. 等待生成完成

### 7. 语音复刻

1. 点击导航栏的"语音复刻"
2. 切换到"创建音色"标签页
3. 上传语音样本（5-30秒清晰录音，WAV/MP3格式）
4. 输入音色前缀（小写字母和数字，<10字符）
5. 点击"创建音色"，等待 1-3 分钟处理
6. 音色就绪后切换到"语音合成"标签页
7. 选择系统音色或自定义音色
8. 输入要合成的文本
9. 调整音量、语速、音高参数
10. 点击"合成语音"获取音频

## 🔑 API Key 说明

### 获取 API Key

访问[阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/)获取 API Key。

### 地域隔离

⚠️ **重要**：北京与新加坡地域的 API Key 独立，不可混用。请确保使用正确地域的 API Key。

## 🎯 模型说明

### 文生视频模型对比

| 模型 | 分辨率 | 时长 | 特性 |
|------|--------|------|------|
| wan2.6-t2v | 720P/1080P | 5/10/15秒 | 有声视频 + 多镜头叙事 |
| wan2.5-t2v-preview | 480P/720P/1080P | 5/10秒 | 有声视频 |
| wan2.2-t2v-plus | 480P/1080P | 5秒 | 专业版 |
| wanx2.1-t2v-turbo | 480P/720P | 5秒 | 极速版 |
| wanx2.1-t2v-plus | 720P | 5秒 | 专业版 |

### 音频功能支持

- **自动配音**：wan2.5 及以上版本支持
- **自定义音频**：上传 MP3/WAV 格式音频文件
- **多镜头叙事**：仅 wan2.6-t2v 支持

### 语音复刻模型

| 模型 | 功能 | 特性 |
|------|------|------|
| cosyvoice-v3-plus | 语音复刻 + 合成 | 高保真音色克隆，支持参数调节 |

### 系统预置音色

| 音色 ID | 名称 | 特点 |
|---------|------|------|
| longanyang | 阳光大男孩 | 男声，活力阳光 |
| longanhuan | 欢脱元气女 | 女声，元气欢快 |

## 🐛 常见问题

### 1. API 调用失败（400 错误）

**问题**：文生视频或图生视频返回 400 错误

**解决方案**：
- 检查 API endpoint 是否正确
- 确认模型名称正确
- 验证参数格式（特别是分辨率格式应为 `832*480` 而非 `832x480`）
- 检查自定义音频 URL 参数位置（应在 `input` 中而非 `parameters` 中）

### 2. 地域隔离问题

**问题**：API Key 无法使用

**解决方案**：
- 确认 API Key 所属地域（北京/新加坡）
- 使用对应地域的 API Key
- 北京与新加坡的 API Key 不可混用

### 3. 视频生成失败

**问题**：视频生成任务一直处于等待状态

**解决方案**：
- 检查网络连接
- 确认 API Key 额度充足
- 查看任务历史中的错误信息
- 重新生成任务

## 📊 技术栈

- **后端框架**：Flask 3.0.0
- **HTTP 客户端**：Requests 2.31.0
- **WSGI 服务器**：Gunicorn + Gevent
- **配置管理**：python-dotenv
- **限流控制**：Flask-Limiter
- **系统监控**：psutil

## 🚀 部署建议

### 生产环境部署

1. **使用 Gunicorn + Gevent**
```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

2. **配置反向代理（Nginx）**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

3. **配置进程管理（Systemd）**
```ini
[Unit]
Description=WanX UI
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/wanx_ui
ExecStart=/path/to/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📄 许可证

请根据项目实际情况添加许可证信息。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件至：[您的邮箱]

---

**注意**：使用本项目需要有效的阿里云通义万相 API Key。请访问[阿里云 DashScope](https://dashscope.console.aliyun.com/)获取。
