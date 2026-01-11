/**
 * 轮询优化器 - 智能调整轮询频率
 * 
 * @author wanx_ui
 * @version 1.0.0
 */

(function(window) {
    'use strict';

    /**
     * 轮询优化器
     */
    const PollingOptimizer = {
        // 配置
        config: {
            defaultInterval: 3000,      // 默认轮询间隔（毫秒）
            minInterval: 2000,          // 最小轮询间隔
            maxInterval: 30000,         // 最大轮询间隔
            idleInterval: 30000,        // 空闲时轮询间隔
            backoffMultiplier: 1.5      // 退避倍数
        },

        // 状态
        state: {
            currentInterval: 3000,      // 当前轮询间隔
            pollingTimer: null,         // 轮询定时器
            isPolling: false,           // 是否正在轮询
            runningTaskCount: 0,        // 进行中的任务数
            lastUpdateTime: 0,          // 上次更新时间
            consecutiveNoChange: 0      // 连续无变化次数
        },

        /**
         * 初始化轮询优化器
         * @param {Function} pollingFunction - 轮询函数
         * @param {Object} options - 配置选项
         */
        init: function(pollingFunction, options) {
            if (options) {
                Object.assign(this.config, options);
            }

            this.pollingFunction = pollingFunction;
            this.state.currentInterval = this.config.defaultInterval;
        },

        /**
         * 开始轮询
         */
        start: function() {
            if (this.state.isPolling) {
                return;
            }

            this.state.isPolling = true;
            this._scheduleNextPoll();
        },

        /**
         * 停止轮询
         */
        stop: function() {
            this.state.isPolling = false;
            if (this.state.pollingTimer) {
                clearTimeout(this.state.pollingTimer);
                this.state.pollingTimer = null;
            }
        },

        /**
         * 更新任务状态
         * @param {Number} runningCount - 进行中的任务数
         * @param {Boolean} hasChanges - 是否有变化
         */
        updateTaskStatus: function(runningCount, hasChanges) {
            const previousCount = this.state.runningTaskCount;
            this.state.runningTaskCount = runningCount;
            this.state.lastUpdateTime = Date.now();

            // 根据任务状态调整轮询间隔
            if (runningCount > 0) {
                // 有进行中的任务，使用较短的轮询间隔
                if (hasChanges) {
                    // 有变化，恢复默认间隔
                    this.state.currentInterval = this.config.defaultInterval;
                    this.state.consecutiveNoChange = 0;
                } else {
                    // 无变化，记录次数
                    this.state.consecutiveNoChange++;
                }
            } else {
                // 无进行中任务，使用较长的轮询间隔或停止轮询
                this.state.currentInterval = this.config.idleInterval;
            }

            // 任务完成时立即刷新一次
            if (previousCount > 0 && runningCount === 0) {
                console.log('[PollingOptimizer] 所有任务已完成，立即刷新');
                this._executePoll();
            }
        },

        /**
         * 计算下次轮询间隔
         * @returns {Number} 轮询间隔（毫秒）
         */
        _calculateInterval: function() {
            const { runningTaskCount, consecutiveNoChange, currentInterval } = this.state;
            const { minInterval, maxInterval, backoffMultiplier, idleInterval } = this.config;

            // 无进行中任务，使用空闲间隔
            if (runningTaskCount === 0) {
                return idleInterval;
            }

            // 有进行中任务但长时间无变化，逐步增加间隔（指数退避）
            if (consecutiveNoChange > 3) {
                const newInterval = Math.min(
                    currentInterval * backoffMultiplier,
                    maxInterval
                );
                console.log(`[PollingOptimizer] 连续${consecutiveNoChange}次无变化，增加轮询间隔至${newInterval}ms`);
                return newInterval;
            }

            // 返回当前间隔
            return Math.max(minInterval, Math.min(currentInterval, maxInterval));
        },

        /**
         * 调度下次轮询
         */
        _scheduleNextPoll: function() {
            if (!this.state.isPolling) {
                return;
            }

            const interval = this._calculateInterval();
            this.state.currentInterval = interval;

            this.state.pollingTimer = setTimeout(() => {
                this._executePoll();
            }, interval);
        },

        /**
         * 执行轮询
         */
        _executePoll: async function() {
            if (!this.state.isPolling || !this.pollingFunction) {
                return;
            }

            try {
                await this.pollingFunction();
            } catch (error) {
                console.error('[PollingOptimizer] 轮询执行失败:', error);
            }

            // 调度下次轮询
            this._scheduleNextPoll();
        },

        /**
         * 立即执行一次轮询
         */
        pollNow: function() {
            if (this.state.pollingTimer) {
                clearTimeout(this.state.pollingTimer);
            }
            this._executePoll();
        }
    };

    // 导出到全局
    window.PollingOptimizer = PollingOptimizer;

})(window);
