// 通用JavaScript工具函数

/**
 * 显示提示消息
 * @param {string} message - 提示消息内容
 * @param {string} type - 消息类型: 'success', 'error', 'info'
 */
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        z-index: 10000;
        max-width: 400px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease;
    `;
    
    const styles = {
        success: 'background: #d4edda; color: #155724; border: 1px solid #c3e6cb;',
        error: 'background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;',
        info: 'background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb;'
    };
    
    alertDiv.style.cssText += styles[type] || styles.info;
    alertDiv.textContent = message;
    
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showAlert('已复制到剪贴板', 'success');
    }).catch(() => {
        showAlert('复制失败', 'error');
    });
}

/**
 * 退出登录
 */
function logout() {
    if (confirm('确定要退出吗?')) {
        fetch('/api/logout', { method: 'POST' })
            .then(() => window.location.href = '/')
            .catch(err => {
                console.error('退出失败:', err);
                showAlert('退出失败', 'error');
            });
    }
}

/**
 * 格式化日期
 * @param {string} dateString - 日期字符串
 * @returns {string} 格式化后的日期
 */
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

/**
 * 格式化时长
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时长
 */
function formatDuration(seconds) {
    return `${seconds}秒`;
}

// ========== 骨架屏工具函数 ==========

/**
 * 生成任务骨架屏HTML
 * @param {number} count - 骨架屏数量，默认3个
 * @returns {string} 骨架屏HTML
 */
function generateTaskSkeleton(count = 3) {
    let html = '';
    for (let i = 0; i < count; i++) {
        html += `
            <div class="task-skeleton">
                <div class="task-skeleton-header">
                    <div class="task-skeleton-title skeleton"></div>
                    <div class="task-skeleton-status skeleton"></div>
                </div>
                <div class="task-skeleton-content skeleton"></div>
                <div class="task-skeleton-footer">
                    <div class="task-skeleton-button skeleton"></div>
                    <div class="task-skeleton-button skeleton"></div>
                    <div class="task-skeleton-button skeleton"></div>
                </div>
            </div>
        `;
    }
    return html;
}

/**
 * 生成缩略图骨架屏HTML
 * @param {number} count - 骨架屏数量，默认5个
 * @returns {string} 骨架屏HTML
 */
function generateThumbnailSkeleton(count = 5) {
    let html = '';
    for (let i = 0; i < count; i++) {
        html += `<div class="thumbnail-skeleton skeleton"></div>`;
    }
    return html;
}

/**
 * 显示任务列表骨架屏
 * @param {string} containerId - 容器元素ID
 * @param {number} count - 骨架屏数量
 */
function showTaskListSkeleton(containerId, count = 3) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = generateTaskSkeleton(count);
    }
}

/**
 * 显示缩略图导航骨架屏
 * @param {string} containerId - 容器元素ID
 * @param {number} count - 骨架屏数量
 */
function showThumbnailSkeleton(containerId, count = 5) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = generateThumbnailSkeleton(count);
    }
}

/**
 * 分阶段加载页面内容
 * @param {Object} options - 配置选项
 * @param {Function} options.stage1 - 阶段1：关键数据加载（0-500ms）
 * @param {Function} options.stage2 - 阶段2：缩略图数据加载（500-1000ms）
 * @param {Function} options.stage3 - 阶段3：次要功能加载（1000ms后）
 */
async function stageLoadPage(options) {
    const { stage1, stage2, stage3 } = options;

    try {
        // 阶段1：关键数据（立即执行）
        if (typeof stage1 === 'function') {
            await stage1();
        }

        // 阶段2：缩略图数据（延迟100ms，让UI先渲染）
        if (typeof stage2 === 'function') {
            setTimeout(async () => {
                await stage2();
            }, 100);
        }

        // 阶段3：次要功能（延迟500ms）
        if (typeof stage3 === 'function') {
            setTimeout(async () => {
                await stage3();
            }, 500);
        }
    } catch (error) {
        console.error('[ERROR] 分阶段加载失败:', error);
    }
}

/**
 * 获取任务状态文本
 * @param {string} status - 任务状态
 * @returns {string} 状态文本
 */
function getStatusText(status) {
    const statusMap = {
        'PENDING': '等待中',
        'RUNNING': '处理中',
        'SUCCEEDED': '成功',
        'FAILED': '失败'
    };
    return statusMap[status] || status;
}

/**
 * 处理图片加载错误
 * @param {HTMLImageElement} imgElement - 图片元素
 * @param {string} url - 图片URL
 */
function handleImageError(imgElement, url) {
    console.error('[ERROR] 图片加载失败:', url);
    imgElement.alt = '图片加载失败';
    imgElement.style.backgroundColor = '#f0f0f0';
}

/**
 * 打开图片模态框
 * @param {string} imageUrl - 图片URL
 */
function openImageModal(imageUrl) {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    
    if (modal && modalImage) {
        modalImage.src = imageUrl;
        modal.classList.add('active');
    }
}

/**
 * 关闭图片模态框
 */
function closeImageModal() {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    
    if (modal && modalImage) {
        modalImage.src = '';
        modal.classList.remove('active');
    }
}

/**
 * 打开视频模态框
 * @param {string} videoUrl - 视频URL
 */
function openVideoModal(videoUrl) {
    const modal = document.getElementById('videoModal');
    const modalVideo = document.getElementById('modalVideo');
    
    if (modal && modalVideo) {
        modalVideo.src = videoUrl;
        modal.classList.add('active');
        modalVideo.play();
    }
}

/**
 * 关闭视频模态框
 */
function closeVideoModal() {
    const modal = document.getElementById('videoModal');
    const modalVideo = document.getElementById('modalVideo');
    
    if (modal && modalVideo) {
        modalVideo.pause();
        modalVideo.src = '';
        modal.classList.remove('active');
    }
}

// 添加滑入滑出动画
if (!document.querySelector('style#common-animations')) {
    const style = document.createElement('style');
    style.id = 'common-animations';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
        
        /* 保存到资产库弹窗样式 */
        .save-to-asset-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 10002;
            justify-content: center;
            align-items: center;
        }
        
        .save-to-asset-modal.active {
            display: flex;
        }
        
        .save-to-asset-content {
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 400px;
            width: 90%;
            box-shadow: 0 20px 50px rgba(0,0,0,0.4);
        }
        
        .save-to-asset-content h3 {
            margin: 0 0 20px 0;
            font-size: 18px;
        }
        
        .save-to-asset-options {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .save-to-asset-option {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            border: 2px solid #eee;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .save-to-asset-option:hover {
            border-color: #1664ff;
            background: #f8f9ff;
        }
        
        .save-to-asset-option.selected {
            border-color: #1664ff;
            background: #e8f0ff;
        }
        
        .save-to-asset-option.disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .save-to-asset-option input {
            margin-right: 12px;
        }
        
        .save-to-asset-option .option-icon {
            font-size: 20px;
            margin-right: 10px;
        }
        
        .save-to-asset-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
    `;
    document.head.appendChild(style);
}

/**
 * 打开保存到资产库弹窗
 * @param {Object} options - 配置选项
 * @param {Array} options.files - 要保存的文件列表 [{filename, source_type, file_type}]
 * @param {string} options.fileType - 文件类型 'image' 或 'video'
 * @param {Function} options.onComplete - 完成回调
 */
function openSaveToAssetModal(options = {}) {
    const { files = [], fileType = 'image', onComplete } = options;
    
    if (files.length === 0) {
        showAlert('请先选择要保存的文件', 'info');
        return;
    }
    
    // 移除旧的弹窗
    const oldModal = document.getElementById('saveToAssetModal');
    if (oldModal) oldModal.remove();
    
    // 创建弹窗
    const modal = document.createElement('div');
    modal.id = 'saveToAssetModal';
    modal.className = 'save-to-asset-modal';
    
    const isVideo = fileType === 'video';
    
    modal.innerHTML = `
        <div class="save-to-asset-content">
            <h3>📁 保存到资产库</h3>
            <p style="margin-bottom: 16px; color: #666; font-size: 14px;">已选择 ${files.length} 个${isVideo ? '视频' : '图片'}，请选择目标子库：</p>
            
            <div class="save-to-asset-options">
                ${isVideo ? `
                    <label class="save-to-asset-option selected" data-category="video">
                        <input type="radio" name="targetCategory" value="video" checked>
                        <span class="option-icon">🎬</span>
                        <span>视频库</span>
                    </label>
                ` : `
                    <label class="save-to-asset-option selected" data-category="storyboard">
                        <input type="radio" name="targetCategory" value="storyboard" checked>
                        <span class="option-icon">🎬</span>
                        <span>分镜库</span>
                    </label>
                    <label class="save-to-asset-option" data-category="artwork">
                        <input type="radio" name="targetCategory" value="artwork">
                        <span class="option-icon">🎨</span>
                        <span>原画库</span>
                    </label>
                `}
            </div>
            
            <div class="save-to-asset-actions">
                <button class="btn btn-secondary" onclick="closeSaveToAssetModal()">取消</button>
                <button class="btn btn-primary" id="confirmSaveToAssetBtn">确认保存</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 绑定选项点击事件
    modal.querySelectorAll('.save-to-asset-option').forEach(option => {
        option.addEventListener('click', () => {
            modal.querySelectorAll('.save-to-asset-option').forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');
            option.querySelector('input').checked = true;
        });
    });
    
    // 绑定确认按钮
    modal.querySelector('#confirmSaveToAssetBtn').addEventListener('click', async () => {
        const selectedCategory = modal.querySelector('input[name="targetCategory"]:checked').value;
        const btn = modal.querySelector('#confirmSaveToAssetBtn');
        
        btn.disabled = true;
        btn.textContent = '保存中...';
        
        let successCount = 0;
        
        for (const file of files) {
            try {
                const response = await fetch('/api/assets/save-from-output', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_type: file.source_type,
                        filename: file.filename,
                        target_category: selectedCategory,
                        file_type: file.file_type || fileType
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    successCount++;
                }
            } catch (error) {
                console.error('保存失败:', file.filename, error);
            }
        }
        
        closeSaveToAssetModal();
        
        if (successCount > 0) {
            const categoryNames = { storyboard: '分镜库', artwork: '原画库', video: '视频库' };
            showAlert(`成功保存 ${successCount} 个文件到${categoryNames[selectedCategory]}`, 'success');
        } else {
            showAlert('保存失败，请重试', 'error');
        }
        
        if (onComplete) {
            onComplete(successCount);
        }
    });
    
    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeSaveToAssetModal();
        }
    });
    
    // 显示弹窗
    modal.classList.add('active');
}

/**
 * 关闭保存到资产库弹窗
 */
function closeSaveToAssetModal() {
    const modal = document.getElementById('saveToAssetModal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 200);
    }
}
