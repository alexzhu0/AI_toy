let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let socket;

const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const status = document.getElementById('status');
const chatBox = document.getElementById('chatBox');
const errorMessage = document.getElementById('errorMessage');

// 检查浏览器支持
function checkBrowserSupport() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('您的浏览器不支持录音功能');
    }
    if (!window.WebSocket) {
        throw new Error('您的浏览器不支持WebSocket');
    }
}

// 检查HTTPS
function checkHttps() {
    if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
        throw new Error('录音功能需要HTTPS连接');
    }
}

// 初始化WebSocket
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        console.log('WebSocket连接已建立');
        startButton.disabled = false;
        status.textContent = '准备就绪';
    };
    
    socket.onmessage = async (event) => {
        const response = JSON.parse(event.data);
        
        if (response.type === 'error') {
            showError(response.content);
            return;
        }
        
        if (response.type === 'text') {
            // 显示文本响应
            addMessage(response.content, 'ai');
        }
        
        if (response.type === 'audio') {
            try {
                // 播放音频响应
                const audioData = base64ToBlob(response.content, 'audio/mp3');
                const audioUrl = URL.createObjectURL(audioData);
                const audio = new Audio(audioUrl);
                
                // 设置音频参数
                audio.volume = 1.0;  // 最大音量
                
                // 添加事件监听
                audio.addEventListener('playing', () => {
                    console.log('开始播放音频');
                    status.textContent = '正在播放回复...';
                });
                
                audio.addEventListener('ended', () => {
                    console.log('音频播放完成');
                    status.textContent = '准备就绪';
                    URL.revokeObjectURL(audioUrl);
                });
                
                audio.addEventListener('error', (e) => {
                    console.error('音频播放错误:', e);
                    status.textContent = '音频播放失败';
                    showError('音频播放失败，请重试');
                    URL.revokeObjectURL(audioUrl);
                });
                
                // 播放音频
                await audio.play();
            } catch (error) {
                console.error('音频播放错误:', error);
                showError('音频播放失败：' + error.message);
                status.textContent = '音频播放失败';
            }
        }
    };
    
    socket.onclose = () => {
        console.log('WebSocket连接已关闭');
        startButton.disabled = true;
        status.textContent = '连接已断开';
        showError('连接已断开，请刷新页面重试');
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket错误:', error);
        showError('连接出错，请刷新页面重试');
    };
}

// 请求麦克风权限
async function requestMicrophonePermission() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        return stream;
    } catch (error) {
        if (error.name === 'NotAllowedError') {
            throw new Error('请允许使用麦克风');
        } else if (error.name === 'NotFoundError') {
            throw new Error('未找到麦克风设备');
        } else if (error.name === 'NotReadableError') {
            throw new Error('麦克风被其他应用程序占用');
        } else {
            throw new Error(`麦克风访问错误: ${error.message}`);
        }
    }
}

// 开始录音
async function startRecording() {
    try {
        // 检查支持
        checkBrowserSupport();
        checkHttps();
        
        // 请求麦克风权限
        const stream = await requestMicrophonePermission();
        
        // 创建MediaRecorder
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm'
        });
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            socket.send(audioBlob);
            audioChunks = [];
        };
        
        // 开始录音
        mediaRecorder.start();
        isRecording = true;
        
        // 更新UI
        startButton.disabled = true;
        stopButton.disabled = false;
        status.textContent = '正在录音...';
        hideError();
        
    } catch (error) {
        showError(error.message);
        console.error('开始录音时出错:', error);
    }
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        
        // 停止所有音轨
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
        
        // 更新UI
        startButton.disabled = false;
        stopButton.disabled = true;
        status.textContent = '录音已停止';
    }
}

// 添加消息到聊天框
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    messageDiv.textContent = content;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 显示错误信息
function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
}

// 隐藏错误信息
function hideError() {
    errorMessage.style.display = 'none';
}

// Base64转Blob
function base64ToBlob(base64, type) {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return new Blob([bytes], { type: type });
}

// 事件监听
startButton.addEventListener('click', startRecording);
stopButton.addEventListener('click', stopRecording);

// 初始化
window.addEventListener('load', () => {
    try {
        initWebSocket();
    } catch (error) {
        showError(error.message);
        console.error('初始化失败:', error);
    }
});
