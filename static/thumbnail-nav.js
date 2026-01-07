/**
 * 通用缩略图快速导航组件 - 虚拟滚动优化版本
 * 用于在历史记录面板中提供快速定位功能
 * 
 * @author wanx_ui
 * @version 2.0.0 - 支持虚拟滚动和懒加载
 */

(function(window) {
    'use strict';

    /**
     * 缩略图导航组件
     */
    const ThumbnailNav = {
        // 配置选项
        config: {
            apiEndpoint: '/api/video-thumbnails',  // API接口地址
            mediaType: 'video',                     // 媒体类型: 'video' 或 'image'
            itemsPerPage: 50,                       // 每页加载数量
            enableBatchSupport: true,               // 是否支持批量任务
            scrollThreshold: 50,                    // 触发加载的距离阈值(px)
            highlightDuration: 1500,                // 高亮持续时间(ms)
            emptyText: '暂无已完成<br>的内容',      // 空状态文本
            countElementId: 'thumbNavCount',        // 计数元素ID
            listElementId: 'thumbnailNavList',      // 列表元素ID
            taskListElementId: 'taskList',          // 任务列表元素ID
            // 虚拟滚动配置
            virtualScrollEnabled: true,             // 是否启用虚拟滚动
            itemHeight: 120,                        // 缩略图项高度(px)
            bufferSize: 5,                          // 上下缓冲区大小
            preloadDistance: 1.5,                   // 预加载距离（屏）
            maxConcurrentLoads: 6,                  // 最大并发加载数
            // 请求合并配置
            useMergedRequest: false,                // 是否使用合并请求（从任务列表获取缩略图）
            tasksApiEndpoint: '/api/tasks'          // 任务列表API地址
        },

        // 状态变量
        state: {
            allThumbnails: [],           // 存储所有已加载的缩略图数据
            thumbNavPage: 1,             // 当前页码
            thumbNavHasMore: true,       // 是否还有更多数据
            isLoadingThumbnails: false,  // 是否正在加载中
            isLoadingAllTasks: false,    // 是否正在加载所有任务
            syncTimeout: null,           // 同步定时器
            // 虚拟滚动状态
            visibleRange: { start: 0, end: 0 },  // 当前可见范围
            scrollTop: 0,                // 当前滚动位置
            containerHeight: 0,          // 容器高度
            loadingImages: new Set(),    // 正在加载的图片集合
            imageObserver: null,         // Intersection Observer实例
            lastScrollTime: 0,           // 上次滚动时间
            scrollDirection: 'down'      // 滚动方向
        },

        /**
         * 初始化组件
         * @param {Object} options - 配置选项
         */
        init: function(options) {
            // 合并配置
            if (options) {
                Object.assign(this.config, options);
            }

            // 重置状态
            this.resetState();

            // 初始化Intersection Observer
            this.initImageObserver();

            // 初始化虚拟滚动
            if (this.config.virtualScrollEnabled) {
                this.initVirtualScroll();
            } else {
                // 传统无限滚动
                this.initThumbnailNavScroll();
            }

            // 初始化二向同步
            this.initThumbnailNavSync();

            // 加载首页数据
            this.loadThumbnails(true);
        },

        /**
         * 重置状态
         */
        resetState: function() {
            this.state.allThumbnails = [];
            this.state.thumbNavPage = 1;
            this.state.thumbNavHasMore = true;
            this.state.isLoadingThumbnails = false;
            this.state.isLoadingAllTasks = false;
            this.state.visibleRange = { start: 0, end: 0 };
            this.state.scrollTop = 0;
            this.state.loadingImages.clear();
        },
        
        /**
         * 检查是否正在加载中
         * @returns {Boolean} 是否正在加载
         */
        isLoading: function() {
            return this.state.isLoadingThumbnails || this.state.isLoadingAllTasks;
        },

        /**
         * 初始化Intersection Observer用于图片懒加载
         */
        initImageObserver: function() {
            if ('IntersectionObserver' in window) {
                const options = {
                    root: document.getElementById(this.config.listElementId),
                    rootMargin: `${this.config.itemHeight * this.config.preloadDistance}px`,
                    threshold: 0.01
                };

                this.state.imageObserver = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            const img = entry.target;
                            const src = img.dataset.src;
                            if (src && !img.src) {
                                this.loadImage(img, src);
                            }
                        }
                    });
                }, options);
            }
        },

        /**
         * 加载图片
         * @param {HTMLElement} img - 图片元素
         * @param {String} src - 图片地址
         */
        loadImage: function(img, src) {
            // 如果已经有 src 或正在加载，跳过
            if (img.src || img.dataset.loading === 'true') return;
            
            img.dataset.loading = 'true';
            
            const loadImg = new Image();
            loadImg.onload = () => {
                img.src = src;
                img.removeAttribute('data-loading');
            };
            loadImg.onerror = () => {
                img.src = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 9'><rect fill='%23e0e0e0' width='16' height='9'/></svg>";
                img.removeAttribute('data-loading');
            };
            loadImg.src = src;
        },

        /**
         * 初始化虚拟滚动
         */
        initVirtualScroll: function() {
            const navList = document.getElementById(this.config.listElementId);
            if (!navList) return;

            // 设置容器高度
            this.state.containerHeight = navList.clientHeight;

            // 监听滚动事件
            let scrollTimeout;
            navList.addEventListener('scroll', () => {
                const currentScrollTop = navList.scrollTop;
                
                // 检测滚动方向
                if (currentScrollTop > this.state.scrollTop) {
                    this.state.scrollDirection = 'down';
                } else if (currentScrollTop < this.state.scrollTop) {
                    this.state.scrollDirection = 'up';
                }
                
                this.state.scrollTop = currentScrollTop;
                this.state.lastScrollTime = Date.now();

                // 防抖处理
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    this.updateVisibleItems();
                    this.checkLoadMore();
                }, 50);

                // 立即更新可见项（简单更新）
                requestAnimationFrame(() => {
                    this.updateVisibleItems();
                });
            });

            // 监听窗口大小变化
            window.addEventListener('resize', () => {
                this.state.containerHeight = navList.clientHeight;
                this.updateVisibleItems();
            });
        },

        /**
         * 计算可见范围
         * @returns {Object} {start, end}
         */
        calculateVisibleRange: function() {
            const { scrollTop } = this.state;
            let { containerHeight } = this.state;
            const { itemHeight, bufferSize } = this.config;
            const totalItems = this.state.allThumbnails.length;

            if (totalItems === 0) {
                return { start: 0, end: 0 };
            }

            // 确保容器高度有效（首次加载时可能为0）
            if (containerHeight <= 0) {
                const navList = document.getElementById(this.config.listElementId);
                if (navList) {
                    containerHeight = navList.clientHeight || 400; // 默认400px
                    this.state.containerHeight = containerHeight;
                }
            }

            // 计算可见区域
            const visibleStart = Math.floor(scrollTop / itemHeight);
            const visibleCount = Math.max(5, Math.ceil(containerHeight / itemHeight)); // 至少显示5个
            const visibleEnd = visibleStart + visibleCount;

            // 加上缓冲区
            const start = Math.max(0, visibleStart - bufferSize);
            const end = Math.min(totalItems, visibleEnd + bufferSize);

            return { start, end };
        },

        /**
         * 更新可见项目
         * @param {Boolean} force - 是否强制渲染
         */
        updateVisibleItems: function(force = false) {
            if (!this.config.virtualScrollEnabled) return;

            const newRange = this.calculateVisibleRange();
            const oldRange = this.state.visibleRange;

            // 如果范围没有变化且非强制，不重新渲染
            if (!force && newRange.start === oldRange.start && newRange.end === oldRange.end) {
                return;
            }

            this.state.visibleRange = newRange;
            this.renderVirtualItems();
        },

        /**
         * 渲染虚拟滚动项目
         */
        renderVirtualItems: function() {
            const navList = document.getElementById(this.config.listElementId);
            if (!navList) return;

            const { start, end } = this.state.visibleRange;
            const { itemHeight } = this.config;
            const totalItems = this.state.allThumbnails.length;

            if (totalItems === 0) {
                navList.innerHTML = `<div class="thumbnail-nav-empty">${this.config.emptyText}</div>`;
                return;
            }

            // 总高度
            const totalHeight = totalItems * itemHeight;
            
            // 占位元素高度
            const offsetY = start * itemHeight;

            // 生成HTML
            const visibleItems = this.state.allThumbnails.slice(start, end);
            const itemsHtml = visibleItems.map((item, idx) => {
                const globalIdx = start + idx + 1;
                let batchLabel = '';
                if (this.config.enableBatchSupport && item.batch_id) {
                    const completed = item.batch_completed || 1;
                    const total = item.batch_total || 1;
                    if (total > 1) {
                        batchLabel = ` <span class="batch-info">(${completed}/${total})</span>`;
                    }
                }

                const mediaTag = this.config.mediaType === 'video' ? 
                    '<span class="thumb-type">视频</span>' : '';

                return `
                    <div class="thumbnail-nav-item" 
                         data-task-id="${item.task_id}"
                         data-batch-id="${item.batch_id || ''}"
                         onclick="ThumbnailNav.scrollToTaskByTaskId('${item.task_id}')">
                        <img data-src="${item.poster_url}" 
                             alt="缩略图" 
                             loading="lazy" 
                             class="thumb-img">
                        <span class="thumb-index">${globalIdx}${batchLabel}</span>
                        ${mediaTag}
                    </div>
                `;
            }).join('');

            // 更新DOM
            navList.innerHTML = `
                <div class="virtual-scroll-spacer" style="height: ${totalHeight}px;">
                    <div class="virtual-scroll-content" style="transform: translateY(${offsetY}px);">
                        ${itemsHtml}
                    </div>
                </div>
            `;

            // 加载更多指示器
            if (this.state.thumbNavHasMore && end >= totalItems - 5) {
                navList.insertAdjacentHTML('beforeend', 
                    '<div class="thumbnail-nav-load-more">加载更多...</div>');
            }

            // 直接加载可见区域的图片
            const self = this;
            const images = navList.querySelectorAll('img[data-src]');
            images.forEach((img, index) => {
                const src = img.dataset.src;
                if (src && !img.src) {
                    // 错开加载避免同时请求太多
                    setTimeout(() => {
                        self.loadImage(img, src);
                    }, index * 30);
                }
            });
        },

        /**
         * 检查是否需要加载更多（智能预加载）
         */
        checkLoadMore: function() {
            const { end } = this.state.visibleRange;
            const totalItems = this.state.allThumbnails.length;
            const { scrollDirection } = this.state;
            
            // 根据滚动方向调整预加载阈值
            let threshold = 10; // 默认提前10个
            
            // 智能预加载算法
            const timeSinceLastScroll = Date.now() - this.state.lastScrollTime;
            const isScrolling = timeSinceLastScroll < 200; // 200ms内算正在滚动
            
            if (scrollDirection === 'down') {
                // 向下滚动：更积极预加载
                if (isScrolling) {
                    threshold = 5; // 快速滚动时减少预加载范围
                } else {
                    threshold = 15; // 停止滚动时增加预加载范围
                }
            } else if (scrollDirection === 'up') {
                // 向上滚动：适度预加载
                threshold = 8;
            }

            if (end >= totalItems - threshold && this.state.thumbNavHasMore && !this.state.isLoadingThumbnails) {
                this.loadThumbnails(false);
            }
        },
        /**
         * 加载缩略图数据（支持分页）
         * @param {Boolean} reset - 是否重新加载
         */
        loadThumbnails: async function(reset = false) {
            if (this.state.isLoadingThumbnails) return;
            if (!reset && !this.state.thumbNavHasMore) return;

            this.state.isLoadingThumbnails = true;

            try {
                const navList = document.getElementById(this.config.listElementId);
                const countSpan = document.getElementById(this.config.countElementId);

                if (reset) {
                    this.state.thumbNavPage = 1;
                    this.state.thumbNavHasMore = true;
                    this.state.allThumbnails = [];
                    if (navList) {
                        navList.innerHTML = '<div class="thumbnail-nav-loading">加载中...</div>';
                    }
                }

                const response = await fetch(
                    `${this.config.apiEndpoint}?page=${this.state.thumbNavPage}&limit=${this.config.itemsPerPage}`
                );
                const data = await response.json();

                if (data.success) {
                    this.state.thumbNavHasMore = data.has_more;

                    if (reset) {
                        this.state.allThumbnails = data.thumbnails;
                    } else {
                        // 追加数据
                        this.state.allThumbnails = this.state.allThumbnails.concat(data.thumbnails);
                    }

                    // 更新计数
                    if (countSpan) {
                        countSpan.textContent = data.total_tasks || this.state.allThumbnails.length;
                    }

                    this.state.thumbNavPage++;

                    // 使用虚拟滚动或传统渲染
                    if (this.config.virtualScrollEnabled) {
                        this.updateVisibleItems(true); // 强制渲染
                    } else {
                        if (reset) {
                            this.renderThumbnails();
                        } else {
                            this.appendThumbnails(data.thumbnails);
                        }
                    }
                } else {
                    if (reset && navList) {
                        navList.innerHTML = '<div class="thumbnail-nav-empty">加载失败</div>';
                    }
                }
            } catch (error) {
                console.error('加载缩略图失败:', error);
                if (reset) {
                    const navList = document.getElementById(this.config.listElementId);
                    if (navList) {
                        navList.innerHTML = '<div class="thumbnail-nav-empty">加载失败</div>';
                    }
                }
            } finally {
                this.state.isLoadingThumbnails = false;
            }
        },

        /**
         * 渲染缩略图（初始渲染）
         */
        renderThumbnails: function() {
            const navList = document.getElementById(this.config.listElementId);
            if (!navList) return;

            if (this.state.allThumbnails.length === 0) {
                navList.innerHTML = `<div class="thumbnail-nav-empty">${this.config.emptyText}</div>`;
                return;
            }

            const mediaTag = this.config.mediaType === 'video' ? 
                '<span class="thumb-type">视频</span>' : '';

            navList.innerHTML = this.state.allThumbnails.map((item, idx) => {
                // 批次信息显示：如果是批次任务，显示"完成数/总数"
                let batchLabel = '';
                if (this.config.enableBatchSupport && item.batch_id) {
                    const completed = item.batch_completed || 1;
                    const total = item.batch_total || 1;
                    if (total > 1) {
                        batchLabel = ` <span class="batch-info">(${completed}/${total})</span>`;
                    }
                }
                return `
                    <div class="thumbnail-nav-item" 
                         data-task-id="${item.task_id}"
                         data-batch-id="${item.batch_id || ''}"
                         onclick="ThumbnailNav.scrollToTaskByTaskId('${item.task_id}')">
                        <img src="${item.poster_url}" 
                             alt="缩略图" 
                             loading="lazy" 
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23e0e0e0%22 width=%2216%22 height=%229%22/></svg>'">
                        <span class="thumb-index">${idx + 1}${batchLabel}</span>
                        ${mediaTag}
                    </div>
                `;
            }).join('');

            // 如果还有更多，添加加载更多指示器
            if (this.state.thumbNavHasMore) {
                navList.innerHTML += '<div class="thumbnail-nav-load-more" id="thumbLoadMoreIndicator">滚动加载更多...</div>';
            }
        },

        /**
         * 追加缩略图（无限滚动时）
         * @param {Array} newItems - 新的缩略图数据
         */
        appendThumbnails: function(newItems) {
            const navList = document.getElementById(this.config.listElementId);
            if (!navList) return;

            // 移除旧的加载指示器
            const loadMoreIndicator = document.getElementById('thumbLoadMoreIndicator');
            if (loadMoreIndicator) {
                loadMoreIndicator.remove();
            }

            // 计算起始索引
            const startIdx = this.state.allThumbnails.length - newItems.length;

            const mediaTag = this.config.mediaType === 'video' ? 
                '<span class="thumb-type">视频</span>' : '';

            // 追加新的缩略图
            const html = newItems.map((item, idx) => {
                const globalIdx = startIdx + idx + 1;
                // 批次信息显示：如果是批次任务，显示"完成数/总数"
                let batchLabel = '';
                if (this.config.enableBatchSupport && item.batch_id) {
                    const completed = item.batch_completed || 1;
                    const total = item.batch_total || 1;
                    if (total > 1) {
                        batchLabel = ` <span class="batch-info">(${completed}/${total})</span>`;
                    }
                }
                return `
                    <div class="thumbnail-nav-item" 
                         data-task-id="${item.task_id}"
                         data-batch-id="${item.batch_id || ''}"
                         onclick="ThumbnailNav.scrollToTaskByTaskId('${item.task_id}')">
                        <img src="${item.poster_url}" 
                             alt="缩略图" 
                             loading="lazy" 
                             onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 9%22><rect fill=%22%23e0e0e0%22 width=%2216%22 height=%229%22/></svg>'">
                        <span class="thumb-index">${globalIdx}${batchLabel}</span>
                        ${mediaTag}
                    </div>
                `;
            }).join('');

            navList.insertAdjacentHTML('beforeend', html);

            // 如果还有更多，添加加载更多指示器
            if (this.state.thumbNavHasMore) {
                navList.insertAdjacentHTML('beforeend', '<div class="thumbnail-nav-load-more" id="thumbLoadMoreIndicator">滚动加载更多...</div>');
            }
        },

        /**
         * 初始化缩略图导航的无限滚动
         */
        initThumbnailNavScroll: function() {
            const navList = document.getElementById(this.config.listElementId);
            if (!navList) return;

            const self = this;
            navList.addEventListener('scroll', function() {
                const scrollTop = navList.scrollTop;
                const scrollHeight = navList.scrollHeight;
                const clientHeight = navList.clientHeight;

                // 距离底部阈值时开始加载
                if (scrollHeight - scrollTop - clientHeight < self.config.scrollThreshold) {
                    if (!self.state.isLoadingThumbnails && self.state.thumbNavHasMore) {
                        self.loadThumbnails(false);
                    }
                }
            });
        },

        /**
         * 根据任务ID滚动到对应位置（优化版）
         * @param {String} taskId - 任务ID
         * @param {String} batchId - 批次ID（可选，从缩略图元素获取）
         */
        scrollToTaskByTaskId: async function(taskId, batchId) {
            const taskList = document.getElementById(this.config.taskListElementId);

            // 如果没有传入batchId，尝试从已加载的缩略图数据中获取
            if (!batchId) {
                const thumbItem = this.state.allThumbnails.find(t => t.task_id === taskId);
                if (thumbItem) {
                    batchId = thumbItem.batch_id;
                }
            }

            // 首先尝试查找任务
            let taskItem = this.findTaskItemByTaskId(taskId, batchId);

            // 如果任务已在 DOM 中，直接滚动
            if (taskItem && taskList) {
                this.highlightAndScrollToTask(taskItem, taskId);
            } else {
                // 任务不在 DOM 中，尝试使用索引定位
                const location = await this.locateTaskByApi(taskId);
                
                if (location && location.success) {
                    // 找到了位置信息，加载对应页面
                    if (typeof showAlert === 'function') {
                        showAlert(`正在加载第${location.page}页...`, 'info');
                    }
                    
                    // 加载目标页面（假设页面有loadTasksToPage函数）
                    if (typeof window.loadTasksToPage === 'function') {
                        await window.loadTasksToPage(location.page);
                    } else {
                        // 降级方案：加载更多任务
                        await this.loadAllTasksForNavigation();
                    }
                    
                    // 重新查找
                    taskItem = this.findTaskItemByTaskId(taskId, batchId || location.batch_id);
                    
                    if (taskItem) {
                        this.highlightAndScrollToTask(taskItem, taskId);
                    } else {
                        // 检查是否仍在加载中
                        if (this.isLoading()) {
                            if (typeof showAlert === 'function') {
                                showAlert('仍在加载中，请稍候...', 'info');
                            }
                        } else {
                            if (typeof showAlert === 'function') {
                                showAlert('未找到该任务，可能已被删除', 'warning');
                            }
                        }
                    }
                } else {
                    // 索引失败，使用传统方式
                    if (typeof showAlert === 'function') {
                        showAlert('正在加载更多历史记录...', 'info');
                    }
                    await this.loadAllTasksForNavigation();

                    taskItem = this.findTaskItemByTaskId(taskId, batchId);
                    if (taskItem) {
                        this.highlightAndScrollToTask(taskItem, taskId);
                    } else {
                        // 检查是否仍在加载中
                        if (this.isLoading()) {
                            if (typeof showAlert === 'function') {
                                showAlert('仍在加载中，请稍候...', 'info');
                            }
                        } else {
                            if (typeof showAlert === 'function') {
                                showAlert('未找到该任务，可能已被删除', 'warning');
                            }
                            console.warn(`[ThumbnailNav] 未找到任务: ${taskId}, batchId: ${batchId}`);
                        }
                    }
                }
            }

            // 更新激活状态
            document.querySelectorAll('.thumbnail-nav-item').forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('data-task-id') === taskId) {
                    item.classList.add('active');
                }
            });
        },

        /**
         * 通过API定位任务
         * @param {String} taskId - 任务ID
         * @returns {Promise<Object>} 位置信息
         */
        locateTaskByApi: async function(taskId) {
            try {
                const response = await fetch(`/api/task-locate/${taskId}`);
                const data = await response.json();
                return data;
            } catch (error) {
                console.error('[ThumbnailNav] 定位任务失败:', error);
                return { success: false };
            }
        },

        /**
         * 查找任务元素（支持批量任务）
         * @param {String} taskId - 任务ID
         * @param {String} batchId - 批次ID（可选）
         * @returns {Element|null} 任务元素
         */
        findTaskItemByTaskId: function(taskId, batchId) {
            // 1. 直接通过ID查找
            let taskItem = document.getElementById(`task-${taskId}`);
            if (taskItem) {
                return taskItem;
            }

            // 2. 通过batch_id查找批次容器
            if (batchId) {
                const batchContainer = document.querySelector(`.task-item[data-batch-id="${batchId}"]`);
                if (batchContainer) {
                    return batchContainer;
                }
            }

            // 3. 查找批量任务中的视频缩略图
            const videoThumb = document.querySelector(`[data-video-id="${taskId}"]`);
            if (videoThumb) {
                taskItem = videoThumb.closest('.task-item');
                if (taskItem) {
                    return taskItem;
                }
            }

            // 4. 查找带有data-task-id属性的元素（备用）
            const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
            if (taskElement) {
                taskItem = taskElement.closest('.task-item');
                if (taskItem) {
                    return taskItem;
                }
            }

            // 5. 查找batch-task-row中包含该task_id的元素
            const taskIdSpans = document.querySelectorAll('.task-id');
            for (const span of taskIdSpans) {
                if (span.textContent.trim() === taskId) {
                    taskItem = span.closest('.task-item');
                    if (taskItem) {
                        return taskItem;
                    }
                }
            }

            return null;
        },

        /**
         * 加载所有任务以支持导航
         */
        loadAllTasksForNavigation: async function() {
            if (this.state.isLoadingAllTasks) {
                console.log('[ThumbnailNav] 任务加载中，跳过重复请求');
                return;
            }
            this.state.isLoadingAllTasks = true;

            try {
                // 优先尝试调用页面级别的加载更多任务函数
                if (typeof window.loadMoreTasksUntilFound === 'function') {
                    await window.loadMoreTasksUntilFound();
                    return;
                }
                
                // 如果页面级别函数不存在，尝试自动调用常见的加载更多函数
                const loadMoreFunctions = [
                    'loadMoreTasks',
                    'loadMoreT2VTasks', 
                    'loadMoreKf2vTasks',
                    'loadMoreR2vTasks',
                    'loadMoreT2ITasks',
                    'loadMoreI2ITasks'
                ];
                
                // 尝试找到并调用存在的加载函数
                for (const funcName of loadMoreFunctions) {
                    if (typeof window[funcName] === 'function') {
                        console.log(`[ThumbnailNav] 调用 ${funcName} 加载更多任务`);
                        // 多次调用以确保加载足够的任务
                        for (let i = 0; i < 5; i++) {
                            // 检查是否还有更多任务
                            if (typeof window.hasMoreTasks !== 'undefined' && !window.hasMoreTasks) {
                                console.log('[ThumbnailNav] 没有更多任务可加载');
                                return;
                            }
                            
                            await window[funcName]();
                            
                            // 检查是否仍在加载中
                            if (typeof window.isLoadingMore !== 'undefined' && window.isLoadingMore) {
                                // 等待加载完成
                                await new Promise(resolve => {
                                    const checkInterval = setInterval(() => {
                                        if (!window.isLoadingMore) {
                                            clearInterval(checkInterval);
                                            resolve();
                                        }
                                    }, 100);
                                });
                            }
                            
                            // 给一个短暂的等待时间让DOM更新
                            await new Promise(resolve => setTimeout(resolve, 300));
                        }
                        return;
                    }
                }
                
                console.warn('[ThumbnailNav] 未找到可用的加载更多任务函数');
            } catch (error) {
                console.error('[ThumbnailNav] 加载任务失败:', error);
            } finally {
                this.state.isLoadingAllTasks = false;
            }
        },

        /**
         * 高亮并滚动到指定任务
         * @param {Element} taskItem - 任务元素
         * @param {String} taskId - 任务ID
         */
        highlightAndScrollToTask: function(taskItem, taskId) {
            // 滚动到目标任务
            taskItem.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // 高亮效果
            taskItem.style.transition = 'box-shadow 0.3s, transform 0.3s';
            taskItem.style.boxShadow = '0 0 0 3px #1664ff, 0 4px 12px rgba(22, 100, 255, 0.3)';
            taskItem.style.transform = 'scale(1.01)';

            // 如果是批量任务，还要高亮具体的缩略图
            const videoThumb = taskItem.querySelector(`[data-video-id="${taskId}"]`) ||
                               taskItem.querySelector(`[data-task-id="${taskId}"]`);
            if (videoThumb) {
                videoThumb.style.transition = 'box-shadow 0.3s, transform 0.3s';
                videoThumb.style.boxShadow = '0 0 0 3px #ff6b35';
                videoThumb.style.transform = 'scale(1.05)';

                setTimeout(() => {
                    videoThumb.style.boxShadow = '';
                    videoThumb.style.transform = '';
                }, 2000);
            }

            setTimeout(() => {
                taskItem.style.boxShadow = '';
                taskItem.style.transform = '';
            }, this.config.highlightDuration);
        },

        /**
         * 初始化双向同步
         */
        initThumbnailNavSync: function() {
            const taskList = document.getElementById(this.config.taskListElementId);
            if (!taskList) return;

            const self = this;
            taskList.addEventListener('scroll', function() {
                if (self.state.syncTimeout) clearTimeout(self.state.syncTimeout);
                self.state.syncTimeout = setTimeout(() => {
                    self.syncThumbnailNavActive();
                }, 100);
            });
        },

        /**
         * 同步缩略图导航激活状态
         */
        syncThumbnailNavActive: function() {
            const taskList = document.getElementById(this.config.taskListElementId);
            if (!taskList) return;

            const taskItems = taskList.querySelectorAll('.task-item');
            const listRect = taskList.getBoundingClientRect();
            const centerY = listRect.top + listRect.height / 2;

            let closestTask = null;
            let closestDistance = Infinity;

            taskItems.forEach(item => {
                const rect = item.getBoundingClientRect();
                const itemCenterY = rect.top + rect.height / 2;
                const distance = Math.abs(itemCenterY - centerY);

                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestTask = item;
                }
            });

            if (closestTask) {
                const taskId = closestTask.getAttribute('data-task-id');
                const videoGrid = closestTask.querySelector('.video-grid');

                document.querySelectorAll('.thumbnail-nav-item').forEach(item => {
                    item.classList.remove('active');
                    if (item.getAttribute('data-task-id') === taskId) {
                        item.classList.add('active');
                    }
                    // 如果是批量任务，还要检查批量 ID
                    if (videoGrid && this.config.enableBatchSupport) {
                        const batchId = closestTask.getAttribute('data-batch-id');
                        if (batchId && item.getAttribute('data-batch-id') === batchId) {
                            item.classList.add('active');
                        }
                    }
                });
            }
        },

        /**
         * 刷新缩略图列表
         */
        refresh: function() {
            this.loadThumbnails(true);
        }
    };

    // 导出到全局
    window.ThumbnailNav = ThumbnailNav;

})(window);
