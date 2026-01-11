/**
 * 资产选择器组件
 * 用于在各应用模块中从资产库选择图片
 */

class AssetPicker {
    constructor(options = {}) {
        this.options = {
            title: '从资产库选择',
            category: 'images',  // 'images' (分镜+原画), 'storyboard', 'artwork', 'video', 'all'
            multiple: false,
            maxSelect: 1,
            targetType: 'i2v',  // i2v, kf2v, i2i
            onSelect: null,     // 选择回调
            onCancel: null,     // 取消回调
            ...options
        };
        
        this.selectedAssets = new Set();
        this.currentPage = 1;
        this.hasMore = false;
        this.assets = [];
        this.modal = null;
        
        this.init();
    }
    
    init() {
        // 创建模态框
        this.createModal();
    }
    
    createModal() {
        // 检查是否已存在
        let existingModal = document.getElementById('assetPickerModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const modal = document.createElement('div');
        modal.id = 'assetPickerModal';
        modal.className = 'asset-picker-modal';
        modal.innerHTML = `
            <div class="asset-picker-content">
                <div class="asset-picker-header">
                    <h3>${this.options.title}</h3>
                    <button class="asset-picker-close" onclick="assetPicker.close()">&times;</button>
                </div>
                
                <div class="asset-picker-tabs">
                    <button class="picker-tab active" data-category="storyboard" onclick="assetPicker.switchTab('storyboard')">
                        🎬 分镜库
                    </button>
                    <button class="picker-tab" data-category="artwork" onclick="assetPicker.switchTab('artwork')">
                        🎨 原画库
                    </button>
                </div>
                
                <div class="asset-picker-body">
                    <div id="pickerAssetList" class="picker-asset-grid">
                        <div class="picker-loading">加载中...</div>
                    </div>
                </div>
                
                <div class="asset-picker-footer">
                    <span class="picker-selected-count">已选择 <span id="pickerSelectedCount">0</span> 项</span>
                    <div class="picker-actions">
                        <button class="btn btn-secondary" onclick="assetPicker.close()">取消</button>
                        <button class="btn btn-primary" onclick="assetPicker.confirm()" id="pickerConfirmBtn">
                            确认选择
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.modal = modal;
        
        // 添加样式
        this.addStyles();
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.close();
            }
        });
        
        // ESC关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('active')) {
                this.close();
            }
        });
    }
    
    addStyles() {
        if (document.getElementById('asset-picker-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'asset-picker-styles';
        style.textContent = `
            .asset-picker-modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                z-index: 10001;
                justify-content: center;
                align-items: center;
                backdrop-filter: blur(3px);
            }
            
            .asset-picker-modal.active {
                display: flex;
            }
            
            .asset-picker-content {
                background: white;
                border-radius: 12px;
                width: 90vw;
                max-width: 900px;
                height: 80vh;
                max-height: 700px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                box-shadow: 0 20px 50px rgba(0,0,0,0.4);
            }
            
            .asset-picker-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 20px;
                border-bottom: 1px solid #eee;
            }
            
            .asset-picker-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 600;
            }
            
            .asset-picker-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #666;
                padding: 0 8px;
                transition: color 0.2s;
            }
            
            .asset-picker-close:hover {
                color: #333;
            }
            
            .asset-picker-tabs {
                display: flex;
                padding: 12px 20px;
                gap: 10px;
                border-bottom: 1px solid #eee;
                background: #f9f9f9;
            }
            
            .picker-tab {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 6px;
                background: white;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.2s;
            }
            
            .picker-tab:hover {
                border-color: #1664ff;
                color: #1664ff;
            }
            
            .picker-tab.active {
                background: #1664ff;
                color: white;
                border-color: #1664ff;
            }
            
            .asset-picker-body {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
            }
            
            .picker-asset-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                gap: 12px;
            }
            
            .picker-asset-item {
                position: relative;
                aspect-ratio: 1;
                border-radius: 8px;
                overflow: hidden;
                cursor: pointer;
                border: 3px solid transparent;
                transition: all 0.2s;
            }
            
            .picker-asset-item:hover {
                transform: scale(1.02);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            
            .picker-asset-item.selected {
                border-color: #1664ff;
                box-shadow: 0 0 0 2px rgba(22, 100, 255, 0.3);
            }
            
            .picker-asset-item img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            
            .picker-asset-item .picker-check {
                position: absolute;
                top: 8px;
                right: 8px;
                width: 24px;
                height: 24px;
                background: rgba(255,255,255,0.9);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                transition: opacity 0.2s;
            }
            
            .picker-asset-item:hover .picker-check,
            .picker-asset-item.selected .picker-check {
                opacity: 1;
            }
            
            .picker-asset-item.selected .picker-check {
                background: #1664ff;
                color: white;
            }
            
            .picker-asset-item .asset-name {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                background: linear-gradient(transparent, rgba(0,0,0,0.7));
                color: white;
                padding: 20px 8px 8px;
                font-size: 11px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            
            .picker-loading, .picker-empty {
                grid-column: 1 / -1;
                text-align: center;
                padding: 40px;
                color: #999;
            }
            
            .asset-picker-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 20px;
                border-top: 1px solid #eee;
                background: #f9f9f9;
            }
            
            .picker-selected-count {
                color: #666;
                font-size: 14px;
            }
            
            .picker-actions {
                display: flex;
                gap: 10px;
            }
            
            .picker-load-more {
                grid-column: 1 / -1;
                text-align: center;
                padding: 20px;
            }
            
            @media (max-width: 600px) {
                .asset-picker-content {
                    width: 95vw;
                    height: 90vh;
                }
                
                .picker-asset-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    open(options = {}) {
        // 合并选项
        Object.assign(this.options, options);
        
        // 重置状态
        this.selectedAssets.clear();
        this.currentPage = 1;
        this.assets = [];
        this.currentCategory = 'storyboard';
        
        // 更新标题
        if (this.modal) {
            this.modal.querySelector('h3').textContent = this.options.title || '从资产库选择';
        }
        
        // 显示模态框
        this.modal.classList.add('active');
        
        // 加载资产
        this.loadAssets();
    }
    
    close() {
        this.modal.classList.remove('active');
        if (this.options.onCancel) {
            this.options.onCancel();
        }
    }
    
    switchTab(category) {
        this.currentCategory = category;
        this.currentPage = 1;
        this.assets = [];
        
        // 更新标签样式
        this.modal.querySelectorAll('.picker-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.category === category);
        });
        
        this.loadAssets();
    }
    
    async loadAssets(append = false) {
        const listEl = this.modal.querySelector('#pickerAssetList');
        
        if (!append) {
            listEl.innerHTML = '<div class="picker-loading">加载中...</div>';
        }
        
        try {
            const response = await fetch(`/api/assets/list?category=${this.currentCategory}&page=${this.currentPage}&limit=30`);
            const data = await response.json();
            
            if (data.success) {
                if (!append) {
                    listEl.innerHTML = '';
                    this.assets = [];
                }
                
                if (data.assets.length === 0 && !append) {
                    listEl.innerHTML = `
                        <div class="picker-empty">
                            <p>暂无资产</p>
                            <p style="font-size: 12px; margin-top: 8px;">请先在资产库中上传图片</p>
                        </div>
                    `;
                    return;
                }
                
                this.assets = this.assets.concat(data.assets);
                this.hasMore = data.has_more;
                
                data.assets.forEach(asset => {
                    listEl.appendChild(this.createAssetItem(asset));
                });
                
                // 加载更多按钮
                if (this.hasMore) {
                    const loadMoreDiv = document.createElement('div');
                    loadMoreDiv.className = 'picker-load-more';
                    loadMoreDiv.innerHTML = '<button class="btn btn-secondary btn-sm" onclick="assetPicker.loadMore()">加载更多</button>';
                    listEl.appendChild(loadMoreDiv);
                }
            }
        } catch (error) {
            console.error('加载资产失败:', error);
            listEl.innerHTML = '<div class="picker-empty">加载失败，请重试</div>';
        }
    }
    
    loadMore() {
        // 移除旧的加载更多按钮
        const oldBtn = this.modal.querySelector('.picker-load-more');
        if (oldBtn) oldBtn.remove();
        
        this.currentPage++;
        this.loadAssets(true);
    }
    
    createAssetItem(asset) {
        const div = document.createElement('div');
        div.className = 'picker-asset-item';
        div.dataset.filename = asset.filename;
        div.dataset.category = asset.category;
        div.dataset.url = asset.url;
        
        const isSelected = this.selectedAssets.has(asset.filename);
        if (isSelected) div.classList.add('selected');
        
        div.innerHTML = `
            <img src="${asset.url}" alt="${asset.original_filename}" loading="lazy">
            <div class="picker-check">${isSelected ? '✓' : ''}</div>
            <div class="asset-name">${asset.original_filename}</div>
        `;
        
        div.onclick = () => this.toggleSelect(asset);
        
        return div;
    }
    
    toggleSelect(asset) {
        const maxSelect = this.options.multiple ? this.options.maxSelect : 1;
        
        if (this.selectedAssets.has(asset.filename)) {
            // 取消选择
            this.selectedAssets.delete(asset.filename);
        } else {
            // 选择
            if (!this.options.multiple) {
                // 单选模式，清除之前的选择
                this.selectedAssets.clear();
                this.modal.querySelectorAll('.picker-asset-item.selected').forEach(el => {
                    el.classList.remove('selected');
                    el.querySelector('.picker-check').textContent = '';
                });
            } else if (this.selectedAssets.size >= maxSelect) {
                showAlert(`最多只能选择 ${maxSelect} 项`, 'info');
                return;
            }
            
            this.selectedAssets.add(asset.filename);
        }
        
        // 更新UI
        const item = this.modal.querySelector(`.picker-asset-item[data-filename="${asset.filename}"]`);
        if (item) {
            const isSelected = this.selectedAssets.has(asset.filename);
            item.classList.toggle('selected', isSelected);
            item.querySelector('.picker-check').textContent = isSelected ? '✓' : '';
        }
        
        this.updateSelectedCount();
    }
    
    updateSelectedCount() {
        this.modal.querySelector('#pickerSelectedCount').textContent = this.selectedAssets.size;
    }
    
    async confirm() {
        if (this.selectedAssets.size === 0) {
            showAlert('请先选择资产', 'info');
            return;
        }
        
        // 获取选中的资产信息
        const selected = [];
        for (const filename of this.selectedAssets) {
            const asset = this.assets.find(a => a.filename === filename);
            if (asset) {
                selected.push(asset);
            }
        }
        
        // 复制到上传目录
        const results = [];
        for (const asset of selected) {
            try {
                const response = await fetch('/api/assets/copy-to-upload', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category: asset.category,
                        filename: asset.filename,
                        target_type: this.options.targetType
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    results.push({
                        original: asset,
                        filename: data.filename,
                        url: data.url
                    });
                }
            } catch (error) {
                console.error('复制资产失败:', error);
            }
        }
        
        // 关闭模态框
        this.close();
        
        // 回调
        if (this.options.onSelect && results.length > 0) {
            if (this.options.multiple) {
                this.options.onSelect(results);
            } else {
                this.options.onSelect(results[0]);
            }
        }
    }
}

// 全局实例
let assetPicker = null;

/**
 * 打开资产选择器
 * @param {Object} options - 配置选项
 * @param {string} options.title - 标题
 * @param {string} options.targetType - 目标类型 (i2v, kf2v, i2i)
 * @param {boolean} options.multiple - 是否多选
 * @param {number} options.maxSelect - 最大选择数量
 * @param {Function} options.onSelect - 选择回调
 */
function openAssetPicker(options = {}) {
    if (!assetPicker) {
        assetPicker = new AssetPicker(options);
    }
    assetPicker.open(options);
}
