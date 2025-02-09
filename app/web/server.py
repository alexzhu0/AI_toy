"""Web服务器模块"""
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import asyncio
from pathlib import Path
import ssl
from config.settings import SERVER_CONFIG, USER_CONFIG
from app.core.speech import SpeechProcessor
from app.core.memory import Memory
from app.core.state import StateManager
from app.agent.companion_agent import CompanionAgent
import base64
from fastapi import WebSocketDisconnect
from fastapi.websockets import WebSocketState

class WebServer:
    def __init__(self):
        self.app = FastAPI()
        self.setup_cors()
        self.setup_routes()
        
        # 初始化组件
        self.speech_processor = SpeechProcessor()
        self.memory = Memory()
        self.state_manager = StateManager(USER_CONFIG)
        self.agent = CompanionAgent(
            self.memory,
            self.state_manager,
            self.speech_processor
        )
        
        # 配置
        self.MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
        self.HEARTBEAT_INTERVAL = 30  # 30秒
        
    async def send_heartbeat(self, websocket: WebSocket):
        """发送心跳包"""
        while True:
            try:
                await websocket.send_json({"type": "ping"})
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            except:
                break
    
    def setup_cors(self):
        """设置CORS"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """设置路由"""
        @self.app.get("/")
        async def root():
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>AI伴侣</title>
                <meta charset="utf-8">
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f0f2f5;
                    }
                    .chat-container {
                        background: white;
                        border-radius: 10px;
                        padding: 20px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }
                    .message-container {
                        height: 400px;
                        overflow-y: auto;
                        border: 1px solid #ddd;
                        padding: 10px;
                        margin-bottom: 20px;
                        border-radius: 5px;
                    }
                    .input-container {
                        display: flex;
                        gap: 10px;
                    }
                    input[type="text"] {
                        flex: 1;
                        padding: 10px;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                    }
                    button {
                        padding: 10px 20px;
                        background-color: #1890ff;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                    }
                    button:hover {
                        background-color: #40a9ff;
                    }
                    .message {
                        margin: 10px 0;
                        padding: 10px;
                        border-radius: 5px;
                    }
                    .user-message {
                        background-color: #e6f7ff;
                        margin-left: 20%;
                    }
                    .ai-message {
                        background-color: #f6ffed;
                        margin-right: 20%;
                    }
                </style>
            </head>
            <body>
                <div class="chat-container">
                    <h1>AI伴侣</h1>
                    <div class="message-container" id="messageContainer"></div>
                    <div class="input-container">
                        <input type="text" id="messageInput" placeholder="请输入消息...">
                        <button onclick="sendMessage()">发送</button>
                        <button onclick="startRecording()" id="recordButton">开始录音</button>
                    </div>
                </div>

                <script>
                    let ws = new WebSocket('wss://' + window.location.host + '/ws');
                    let mediaRecorder;
                    let audioChunks = [];
                    let isRecording = false;
                    let lastPingTime = Date.now();
                    let reconnectAttempts = 0;
                    const maxReconnectAttempts = 5;
                    
                    // 心跳检测
                    setInterval(() => {
                        if (Date.now() - lastPingTime > 40000) {  // 40秒没有心跳就重连
                            console.log('重新连接WebSocket...');
                            ws.close();
                            ws = new WebSocket('wss://' + window.location.host + '/ws');
                            setupWebSocket();
                        }
                    }, 5000);
                    
                    function setupWebSocket() {
                        ws.onopen = function() {
                            console.log('WebSocket连接成功');
                            reconnectAttempts = 0;
                        };

                        ws.onmessage = function(event) {
                            lastPingTime = Date.now();
                            const data = JSON.parse(event.data);
                            if (data.type === 'ping') {
                                return;
                            }
                            
                            if (data.type === 'error') {
                                console.error('错误:', data.content);
                                alert('发生错误: ' + data.content);
                                return;
                            }
                            
                            displayMessage(data.content, 'ai');
                            
                            if (data.type === 'audio') {
                                const audio = new Audio('data:audio/mp3;base64,' + data.content);
                                audio.play();
                            }
                        };
                        
                        ws.onclose = function() {
                            console.log('WebSocket连接已关闭');
                            if (reconnectAttempts < maxReconnectAttempts) {
                                const delay = Math.pow(2, reconnectAttempts) * 1000;
                                setTimeout(() => {
                                    console.log(`尝试重新连接 (${reconnectAttempts + 1}/${maxReconnectAttempts})`);
                                    ws = new WebSocket('wss://' + window.location.host + '/ws');
                                    setupWebSocket();
                                    reconnectAttempts++;
                                }, delay);
                            }
                        };
                        
                        ws.onerror = function(error) {
                            console.error('WebSocket错误:', error);
                        };
                    }
                    
                    setupWebSocket();

                    function displayMessage(message, type) {
                        const messageContainer = document.getElementById('messageContainer');
                        const messageDiv = document.createElement('div');
                        messageDiv.className = `message ${type}-message`;
                        messageDiv.textContent = message;
                        messageContainer.appendChild(messageDiv);
                        messageContainer.scrollTop = messageContainer.scrollHeight;
                    }

                    function sendMessage() {
                        const input = document.getElementById('messageInput');
                        const message = input.value.trim();
                        if (message) {
                            ws.send(JSON.stringify({
                                type: 'text',
                                content: message
                            }));
                            displayMessage(message, 'user');
                            input.value = '';
                        }
                    }

                    async function startRecording() {
                        const button = document.getElementById('recordButton');
                        if (!isRecording) {
                            try {
                                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                                mediaRecorder = new MediaRecorder(stream);
                                audioChunks = [];

                                mediaRecorder.ondataavailable = (event) => {
                                    audioChunks.push(event.data);
                                };

                                mediaRecorder.onstop = async () => {
                                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                                    const reader = new FileReader();
                                    reader.readAsDataURL(audioBlob);
                                    reader.onloadend = () => {
                                        const base64Audio = reader.result.split(',')[1];
                                        if (base64Audio.length > 10 * 1024 * 1024) {  // 10MB
                                            alert('音频数据太大，请缩短录音时间');
                                            return;
                                        }
                                        ws.send(JSON.stringify({
                                            type: 'audio',
                                            content: base64Audio
                                        }));
                                    };
                                };

                                mediaRecorder.start();
                                isRecording = true;
                                button.textContent = '停止录音';
                                button.style.backgroundColor = '#ff4d4f';
                            } catch (err) {
                                console.error('录音失败:', err);
                                alert('无法访问麦克风');
                            }
                        } else {
                            mediaRecorder.stop();
                            mediaRecorder.stream.getTracks().forEach(track => track.stop());
                            isRecording = false;
                            button.textContent = '开始录音';
                            button.style.backgroundColor = '#1890ff';
                        }
                    }

                    document.getElementById('messageInput').addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            sendMessage();
                        }
                    });
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
            try:
                while True:
                    # 增加连接状态检查
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        break
                    
                    data = await websocket.receive_json()
                    message_type = data.get("type")
                    
                    # 增加空消息处理
                    if not message_type:
                        await websocket.send_json({
                            "type": "error",
                            "content": "无效的消息格式"
                        })
                        continue
                    
                    if message_type == "text":
                        # 处理文本消息
                        text = data.get("content", "")
                        response = await self.agent.process_text(text)
                        await websocket.send_json({
                            "type": "text",
                            "content": response
                        })
                        
                    elif message_type == "audio":
                        # 处理音频消息
                        audio_base64 = data.get("content", "")
                        if len(audio_base64) > self.MAX_AUDIO_SIZE:
                            await websocket.send_json({
                                "type": "error",
                                "content": "音频数据太大，请缩短录音时间"
                            })
                            continue
                            
                        try:
                            audio_data = base64.b64decode(audio_base64)
                            text = await self.speech_processor.speech_to_text(audio_data)
                            response = await self.agent.process_text(text)
                            audio_response = await self.speech_processor.text_to_speech(response)
                            
                            # 将音频数据转换为base64
                            audio_response_base64 = base64.b64encode(audio_response).decode('utf-8')
                            await websocket.send_json({
                                "type": "audio",
                                "content": audio_response_base64
                            })
                        except Exception as e:
                            await websocket.send_json({
                                "type": "error",
                                "content": f"处理音频时出错: {str(e)}"
                            })
                    
            except WebSocketDisconnect:
                print("WebSocket连接已关闭")
            except Exception as e:
                print(f"WebSocket错误: {e}")
                if not isinstance(e, WebSocketDisconnect):
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "content": str(e)
                        })
                    except:
                        pass
            finally:
                try:
                    heartbeat_task.cancel()
                    await websocket.close()
                except:
                    pass
        
        @self.app.post("/upload-audio")
        async def upload_audio(file: UploadFile = File(...)):
            contents = await file.read()
            if len(contents) > self.MAX_AUDIO_SIZE:
                return {"error": "音频文件太大"}
                
            try:
                text = await self.speech_processor.speech_to_text(contents)
                response = await self.agent.process_text(text)
                audio_response = await self.speech_processor.text_to_speech(response)
                
                return StreamingResponse(
                    iter([audio_response]),
                    media_type="audio/mp3"
                )
            except Exception as e:
                return {"error": str(e)}
    
    async def start(self):
        """启动服务器"""
        config = SERVER_CONFIG
        ssl_config = config.get('ssl', {})
        
        if ssl_config.get('enabled'):
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(
                str(ssl_config['cert_file']),
                str(ssl_config['key_file'])
            )
        else:
            ssl_context = None
        
        config = uvicorn.Config(
            self.app,
            host=config.get('host', '0.0.0.0'),
            port=config.get('port', 8000),
            ssl_certfile=str(ssl_config['cert_file']) if ssl_config.get('enabled') else None,
            ssl_keyfile=str(ssl_config['key_file']) if ssl_config.get('enabled') else None
        )
        
        server = uvicorn.Server(config)
        await server.serve() 