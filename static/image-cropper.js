/**
 * 图片裁剪模块
 * 基于 Cropper.js 实现图片裁剪功能
 */

class ImageCropper {
    constructor() {
        this.cropper = null;
        this.currentFile = null;
        this.currentImageElement = null;
        this.onCropComplete = null;
        this.aspectRatios = {
            'free': NaN,  // NaN 表示自由比例
            '16:9': 16 / 9,
            '9:16': 9 / 16,
            '4:3': 4 / 3,
            '3:4': 3 / 4,
            '1:1': 1
        };
    }

    /**
     * 打开裁剪界面
     * @param {File} file - 图片文件
     * @param {Function} callback - 裁剪完成回调函数，接收裁剪后的 File 对象
     */
    open(file, callback) {
        console.log('打开裁剪界面:', file.name);
        // 验证文件
        if (!this.validateFile(file)) {
            return;
        }

        this.currentFile = file;
        this.onCropComplete = callback;

        // 显示裁剪模态框
        const modal = document.getElementById('cropperModal');
        if (!modal) {
            console.error('裁剪模态框不存在，请确保已添加 HTML 结构');
            return;
        }

        modal.style.display = 'flex';

        // 绑定按钮事件（每次打开时重新绑定）
        this.bindButtons();

        // 加载图片
        this.loadImage(file);
    }

    /**
     * 绑定按钮事件
     */
    bindButtons() {
        console.log('绑定裁剪器按钮事件');
        
        // 纵横比按钮
        const aspectRatioButtons = document.querySelectorAll('.aspect-ratio-btn');
        aspectRatioButtons.forEach(button => {
            // 移除旧的事件监听（避免重复）
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            newButton.addEventListener('click', () => {
                console.log('点击纵横比按钮:', newButton.dataset.ratio);
                aspectRatioButtons.forEach(btn => btn.classList.remove('active'));
                newButton.classList.add('active');
                this.setAspectRatio(newButton.dataset.ratio);
            });
        });

        // 取消按钮
        const cancelBtn = document.getElementById('cropperCancelBtn');
        if (cancelBtn) {
            const newCancelBtn = cancelBtn.cloneNode(true);
            cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
            newCancelBtn.addEventListener('click', () => {
                console.log('点击取消按钮');
                this.close();
            });
        }

        // 确认裁剪按钮
        const confirmBtn = document.getElementById('cropperConfirmBtn');
        if (confirmBtn) {
            const newConfirmBtn = confirmBtn.cloneNode(true);
            confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
            newConfirmBtn.addEventListener('click', () => {
                console.log('点击确认裁剪按钮');
                this.cropImage();
            });
        } else {
            console.error('找不到确认裁剪按钮');
        }
    }

    /**
     * 验证文件
     * @param {File} file 
     * @returns {boolean}
     */
    validateFile(file) {
        // 检查文件类型
        const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            this.showAlert('图片格式不支持，请选择 JPG、PNG、BMP 或 WEBP 格式的图片', 'error');
            return false;
        }

        // 检查文件大小（10MB）
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showAlert('图片文件过大，请选择小于 10MB 的图片', 'error');
            return false;
        }

        return true;
    }

    /**
     * 加载图片到裁剪器
     * @param {File} file 
     */
    loadImage(file) {
        const reader = new FileReader();
        const imageElement = document.getElementById('cropperImage');

        reader.onload = (e) => {
            imageElement.src = e.target.result;
            this.currentImageElement = imageElement;

            // 等待图片加载完成后初始化裁剪器
            imageElement.onload = () => {
                this.initCropper();
                this.setDefaultAspectRatio();
            };
        };

        reader.onerror = () => {
            this.showAlert('图片加载失败，请重试', 'error');
            this.close();
        };

        reader.readAsDataURL(file);
    }

    /**
     * 初始化 Cropper 实例
     */
    initCropper() {
        if (this.cropper) {
            this.cropper.destroy();
        }

        const imageElement = this.currentImageElement;

        this.cropper = new Cropper(imageElement, {
            viewMode: 1,
            dragMode: 'move',
            aspectRatio: 16 / 9, // 默认值,会被智能推荐覆盖
            autoCropArea: 1,  // 裁剪框默认占满整个图片
            responsive: true,
            restore: false,
            guides: true,
            center: true,
            highlight: true,  // 启用高亮显示
            cropBoxMovable: true,
            cropBoxResizable: true,
            toggleDragModeOnDblclick: false,
            minCropBoxWidth: 200,
            minCropBoxHeight: 200,
            modal: true,  // 启用遮罩
            background: true,  // 显示网格背景
        });
    }

    /**
     * 智能设置默认纵横比
     */
    setDefaultAspectRatio() {
        if (!this.currentImageElement) return;

        // 默认使用自定义比例，让用户自由裁剪
        const defaultRatio = 'free';

        // 设置选中状态
        const buttons = document.querySelectorAll('.aspect-ratio-btn');
        buttons.forEach(btn => {
            if (btn.dataset.ratio === defaultRatio) {
                btn.classList.add('active');
                this.setAspectRatio(defaultRatio);
            } else {
                btn.classList.remove('active');
            }
        });
    }

    /**
     * 设置纵横比
     * @param {string} ratioKey - 纵横比键值，如 '16:9' 或 'free'
     */
    setAspectRatio(ratioKey) {
        if (!this.cropper) return;

        const ratio = this.aspectRatios[ratioKey];
        if (ratio !== undefined) {
            this.cropper.setAspectRatio(ratio);  // NaN 会让 cropper 支持自由比例
            console.log('设置纵横比:', ratioKey, ratio);
        }
    }

    /**
     * 执行裁剪
     */
    async cropImage() {
        if (!this.cropper) {
            this.showAlert('裁剪器未初始化', 'error');
            return;
        }

        try {
            console.log('开始裁剪图片...');
            // 获取裁剪后的 Canvas
            const canvas = this.cropper.getCroppedCanvas({
                maxWidth: 2048,
                maxHeight: 2048,
                imageSmoothingEnabled: true,
                imageSmoothingQuality: 'high'
            });

            if (!canvas) {
                throw new Error('无法生成裁剪结果');
            }

            console.log('Canvas 生成成功，尺寸:', canvas.width, 'x', canvas.height);

            // 将 Canvas 转换为 Blob
            const blob = await new Promise((resolve, reject) => {
                canvas.toBlob((blob) => {
                    if (blob) {
                        resolve(blob);
                    } else {
                        reject(new Error('无法生成 Blob'));
                    }
                }, 'image/jpeg', 0.9);
            });

            console.log('Blob 生成成功，大小:', blob.size, 'bytes');

            // 确保文件名有正确的 .jpg 扩展名
            let filename = this.currentFile.name;
            // 移除原有扩展名，添加 .jpg
            if (filename.lastIndexOf('.') > 0) {
                filename = filename.substring(0, filename.lastIndexOf('.')) + '.jpg';
            } else {
                filename = filename + '.jpg';
            }

            // 创建新的 File 对象
            const croppedFile = new File(
                [blob],
                filename,
                { type: 'image/jpeg', lastModified: Date.now() }
            );

            console.log('裁剪后的文件:', croppedFile.name, croppedFile.type, croppedFile.size);

            // 执行回调（先执行回调，再关闭裁剪器）
            if (this.onCropComplete) {
                console.log('调用上传回调...');
                const callback = this.onCropComplete;
                // 关闭裁剪器
                this.close();
                // 执行回调
                await callback(croppedFile);
            } else {
                console.warn('没有回调函数');
                // 关闭裁剪器
                this.close();
            }

        } catch (error) {
            console.error('裁剪失败:', error);
            this.showAlert('裁剪失败，请尝试使用较小的图片', 'error');
        }
    }

    /**
     * 关闭裁剪界面
     */
    close() {
        // 销毁 Cropper 实例
        if (this.cropper) {
            this.cropper.destroy();
            this.cropper = null;
        }

        // 清空图片
        if (this.currentImageElement) {
            this.currentImageElement.src = '';
        }

        // 隐藏模态框
        const modal = document.getElementById('cropperModal');
        if (modal) {
            modal.style.display = 'none';
        }

        // 重置状态
        this.currentFile = null;
        this.currentImageElement = null;
        this.onCropComplete = null;

        // 重置纵横比按钮
        const buttons = document.querySelectorAll('.aspect-ratio-btn');
        buttons.forEach(btn => btn.classList.remove('active'));
    }

    /**
     * 显示提示消息
     * @param {string} message 
     * @param {string} type 
     */
    showAlert(message, type) {
        // 使用全局的 showAlert 函数，如果不存在则使用 alert
        if (typeof window.showAlert === 'function') {
            window.showAlert(message, type);
        } else {
            alert(message);
        }
    }
}

// 创建全局单例
window.imageCropper = new ImageCropper();

// 初始化事件监听器（在 DOM 加载完成后）
document.addEventListener('DOMContentLoaded', function() {
    // 纵横比按钮点击事件
    const aspectRatioButtons = document.querySelectorAll('.aspect-ratio-btn');
    aspectRatioButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 更新选中状态
            aspectRatioButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');

            // 设置纵横比
            const ratio = this.dataset.ratio;
            window.imageCropper.setAspectRatio(ratio);
        });
    });

    // 取消按钮
    const cancelBtn = document.getElementById('cropperCancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            window.imageCropper.close();
        });
    }

    // 确认裁剪按钮
    const confirmBtn = document.getElementById('cropperConfirmBtn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            window.imageCropper.cropImage();
        });
    }

    // 点击遮罩层关闭
    const modal = document.getElementById('cropperModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                window.imageCropper.close();
            }
        });
    }
});
