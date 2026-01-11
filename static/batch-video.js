// 批量视频管理和展示功能

// 切换批量选择模式
function toggleBatchMode() {
    batchModeEnabled = !batchModeEnabled;
    const btn = document.getElementById('batchModeBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const saveToAssetBtn = document.getElementById('saveToAssetBtn');
    
    if (batchModeEnabled) {
        btn.textContent = '取消选择';
        btn.classList.add('active');
        downloadBtn.style.display = 'inline-block';
        if (saveToAssetBtn) saveToAssetBtn.style.display = 'inline-block';
    } else {
        btn.textContent = '批量选择';
        btn.classList.remove('active');
        downloadBtn.style.display = 'none';
        if (saveToAssetBtn) saveToAssetBtn.style.display = 'none';
        selectedVideos.clear();
    }
    
    // 重新渲染任务列表 - 自动检测当前页面的加载函数
    if (typeof loadTasks === 'function') {
        loadTasks();
    } else if (typeof loadKf2vTasks === 'function') {
        loadKf2vTasks();
    } else if (typeof loadI2ITasks === 'function') {
        loadI2ITasks();
    } else if (typeof loadT2ITasks === 'function') {
        loadT2ITasks();
    }
}

// 更新选中数量
function updateSelectedCount() {
    selectedVideos.clear();
    document.querySelectorAll('.batch-checkbox:checked').forEach(checkbox => {
        selectedVideos.add(checkbox.dataset.taskId);
    });
    document.getElementById('selectedCount').textContent = selectedVideos.size;
}

// 下载选中的视频
async function downloadSelected() {
    if (selectedVideos.size === 0) {
        showAlert('请先选择要下载的视频', 'error');
        return;
    }
    
    showAlert(`开始下载 ${selectedVideos.size} 个视频...`, 'success');
    
    for (const taskId of selectedVideos) {
        const task = document.querySelector(`[data-task-id="${taskId}"]`);
        if (task) {
            const video = task.querySelector('video source');
            if (video) {
                downloadVideo(video.src, `video_${taskId}.mp4`);
                await new Promise(resolve => setTimeout(resolve, 500)); // 延迟避免浏览器限制
            }
        }
    }
}

// 下载单个视频文件
function downloadVideo(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// 打开视频放大浮层
function openVideoModal(videoUrl) {
    const modal = document.getElementById('videoModal');
    const modalVideo = document.getElementById('modalVideo');
    
    modalVideo.src = videoUrl;
    modal.classList.add('active');
    modalVideo.play();
}

// 关闭视频放大浮层
function closeVideoModal() {
    const modal = document.getElementById('videoModal');
    const modalVideo = document.getElementById('modalVideo');
    
    modalVideo.pause();
    modalVideo.src = '';
    modal.classList.remove('active');
}

// ESC键关闭浮层
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeVideoModal();
    }
});

// 保存选中的视频到资产库 - kf2v页面使用
function saveSelectedToAssets() {
    if (typeof selectedVideos === 'undefined' || selectedVideos.size === 0) {
        showAlert('请先选择要保存的视频', 'error');
        return;
    }
    
    // 收集选中的视频文件信息
    const files = [];
    
    // 判断是哪个页面
    const isKf2vPage = typeof loadKf2vTasks === 'function';
    const sourceType = isKf2vPage ? 'kf2v' : 'i2v';
    
    for (const id of selectedVideos) {
        // 尝试从多种选择器获取复选框
        let checkbox = document.querySelector(`.batch-checkbox[data-task-id="${id}"]`);
        
        // kf2v页面使用data-video-id
        if (!checkbox) {
            checkbox = document.querySelector(`.batch-checkbox[data-video-id="${id}"]`);
        }
        
        // 其他页面可能使用video-checkbox
        if (!checkbox) {
            checkbox = document.querySelector(`.video-checkbox[data-video-id="${id}"]`);
        }
        
        if (checkbox) {
            let videoUrl = checkbox.dataset.videoUrl;
            
            // 如果没有videoUrl，尝试从任务元素中获取
            if (!videoUrl) {
                const taskId = checkbox.dataset.taskId || id.split('_')[0];
                const taskItem = document.getElementById(`task-${taskId}`);
                if (taskItem) {
                    const video = taskItem.querySelector('video[data-src]');
                    if (video) {
                        videoUrl = video.dataset.src;
                    }
                }
                // 尝试从视频缩略图中获取
                if (!videoUrl) {
                    const videoThumb = document.getElementById(`video-${id}`);
                    if (videoThumb) {
                        const video = videoThumb.querySelector('video[data-src]');
                        if (video) {
                            videoUrl = video.dataset.src;
                        }
                    }
                }
            }
            
            if (videoUrl) {
                const filename = videoUrl.split('/').pop();
                files.push({
                    filename: filename,
                    source_type: sourceType,
                    file_type: 'video'
                });
            }
        }
    }
    
    if (files.length === 0) {
        showAlert('没有找到可保存的视频', 'error');
        return;
    }
    
    openSaveToAssetModal({
        files: files,
        fileType: 'video',
        onComplete: (count) => {
            if (count > 0) {
                selectedVideos.clear();
                if (typeof updateSelectedCount === 'function') {
                    updateSelectedCount();
                }
            }
        }
    });
}
