"""Web服务器模块"""
from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import json
import asyncio
from pathlib import Path
import ssl
import logging
import traceback
from config.settings import SERVER_CONFIG, USER_CONFIG
from app.core.speech import SpeechProcessor
from app.core.memory import Memory
from app.core.state import StateManager
from app.agent.companion_agent import CompanionAgent
import base64
from fastapi import WebSocketDisconnect
from fastapi.websockets import WebSocketState
from typing import Dict, List, Any, Optional, Set
import time
import os
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 添加控制台处理程序
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# 创建格式化程序
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# 添加处理程序到logger
logger.addHandler(ch)

class ConnectionManager:
    """WebSocket连接管理器"""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_info[websocket] = {
            "client_id": client_id or f"client_{len(self.active_connections)}",
            "connected_at": datetime.now().isoformat(),
            "last_activity": time.time()
        }
        logger.info(f"客户端连接: {self.connection_info[websocket]['client_id']}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            client_id = self.connection_info.get(websocket, {}).get("client_id", "unknown")
            logger.info(f"客户端断开连接: {client_id}")
            if websocket in self.connection_info:
                del self.connection_info[websocket]
    
    def update_activity(self, websocket: WebSocket):
        if websocket in self.connection_info:
            self.connection_info[websocket]["last_activity"] = time.time()
    
    async def broadcast(self, message: str):
        """向所有客户端广播消息"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"发送广播消息失败: {e}")
                self.disconnect(connection)
    
    async def cleanup_inactive_connections(self, timeout: int = 120):
        """清理不活跃的连接"""
        now = time.time()
        for ws in list(self.active_connections):
            last_activity = self.connection_info.get(ws, {}).get("last_activity", 0)
            if now - last_activity > timeout:
                logger.info(f"关闭不活跃连接: {self.connection_info.get(ws, {}).get('client_id', 'unknown')}")
                try:
                    await ws.close(code=1000, reason="不活跃超时")
                except:
                    pass
                self.disconnect(ws)

class WebServer:
    def __init__(self):
        self.app = FastAPI(
            title="AI Toy API",
            description="AI伴侣应用的API接口",
            version="1.0.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc"
        )
        self.setup_exception_handlers()
        self.setup_cors()
        self.setup_routes()
        
        # 初始化连接管理器
        self.connection_manager = ConnectionManager()
        
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
        self.CONNECTION_TIMEOUT = 120  # 120秒
        
        # 启动后台任务
        self.background_tasks = set()
    
    def setup_exception_handlers(self):
        """设置全局异常处理"""
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            logger.error(f"未处理的异常: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误", "message": str(exc)}
            )
    
    async def send_heartbeat(self, websocket: WebSocket):
        """发送心跳包"""
        try:
            while True:
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.warning("心跳检测到客户端断开")
                    break
                    
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
                logger.debug("发送心跳包")
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
        except Exception as e:
            logger.error(f"心跳包发送错误: {e}")
        finally:
            self.connection_manager.disconnect(websocket)
    
    async def cleanup_connections_task(self):
        """清理不活跃连接的后台任务"""
        try:
            while True:
                await self.connection_manager.cleanup_inactive_connections(self.CONNECTION_TIMEOUT)
                await asyncio.sleep(60)  # 每分钟检查一次
        except asyncio.CancelledError:
            logger.info("连接清理任务被取消")
        except Exception as e:
            logger.error(f"连接清理任务出错: {e}", exc_info=True)
    
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
        # 挂载静态文件目录
        static_dir = Path(__file__).parent / "static"
        if not static_dir.exists():
            static_dir.mkdir(parents=True)
            
        self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        @self.app.get("/")
        async def root():
            try:
                html_content = (static_dir / "index.html").read_text(encoding='utf-8')
                return HTMLResponse(content=html_content, media_type="text/html")
            except Exception as e:
                logger.error(f"读取index.html失败: {e}")
                return HTMLResponse(content="服务器错误", status_code=500)
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "timestamp": datetime.now().isoformat()}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.connection_manager.connect(websocket)
            
            # 启动心跳任务
            heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
            
            try:
                while True:
                    # 增加连接状态检查
                    if websocket.client_state == WebSocketState.DISCONNECTED:
                        break
                    
                    # 更新最后活动时间
                    self.connection_manager.update_activity(websocket)
                    
                    try:
                        # 接收消息
                        data = await websocket.receive()
                        
                        # 处理二进制音频数据
                        if "bytes" in data:
                            audio_data = data["bytes"]
                            audio_size = len(audio_data)
                            logger.info(f"收到音频数据大小: {audio_size} bytes")
                            
                            # 检查音频数据大小
                            if audio_size > self.MAX_AUDIO_SIZE:
                                logger.error(f"音频数据太大: {audio_size} bytes")
                                await websocket.send_json({
                                    "type": "error",
                                    "content": f"音频数据太大（{audio_size} bytes），最大允许 {self.MAX_AUDIO_SIZE} bytes"
                                })
                                continue
                            
                            if audio_size == 0:
                                logger.error("收到空的音频数据")
                                await websocket.send_json({
                                    "type": "error",
                                    "content": "收到空的音频数据"
                                })
                                continue
                            
                            try:
                                # 语音转文字
                                text = await self.speech_processor.speech_to_text(audio_data)
                                if not text:
                                    logger.error("语音识别结果为空")
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "未能识别语音内容，请重试"
                                    })
                                    continue
                                
                                logger.info(f"语音识别结果: {text}")
                                
                                # 生成响应
                                response = await self.agent.process_text(text)
                                if not response:
                                    logger.error("生成响应为空")
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "生成响应失败"
                                    })
                                    continue
                                
                                logger.info(f"生成的响应: {response}")
                                
                                # 生成语音
                                try:
                                    audio_response = await self.speech_processor.text_to_speech(response)
                                except asyncio.TimeoutError:
                                    logger.error("语音合成超时")
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "语音合成超时，请重试"
                                    })
                                    continue
                                except Exception as e:
                                    logger.error(f"语音合成错误: {e}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "语音合成失败，请重试"
                                    })
                                    continue
                                
                                # 将音频数据转换为base64
                                try:
                                    audio_response_base64 = base64.b64encode(audio_response).decode('utf-8')
                                    logger.debug(f"转换后的base64数据长度: {len(audio_response_base64)}")
                                except Exception as e:
                                    logger.error(f"Base64编码错误: {e}", exc_info=True)
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "音频响应处理错误"
                                    })
                                    continue
                                
                                # 发送响应
                                try:
                                    logger.info("开始发送响应")
                                    await websocket.send_json({
                                        "type": "text",
                                        "content": response
                                    })
                                    await websocket.send_json({
                                        "type": "audio",
                                        "content": audio_response_base64
                                    })
                                    logger.info("响应发送完成")
                                except Exception as e:
                                    logger.error(f"发送响应错误: {e}", exc_info=True)
                                
                            except Exception as e:
                                error_msg = f"处理音频时出错: {str(e)}\n{traceback.format_exc()}"
                                logger.error(error_msg)
                                await websocket.send_json({
                                    "type": "error",
                                    "content": "语音识别出错，请重试"
                                })
                        
                        # 处理文本消息
                        elif "text" in data:
                            json_data = json.loads(data["text"])
                            logger.info(f"收到文本消息: {json_data}")
                            
                            # 处理心跳响应
                            if json_data.get("type") == "pong":
                                logger.debug("收到心跳响应")
                                continue
                            
                            # 处理文本消息
                            if text_content := json_data.get("content"):
                                if not text_content.strip():
                                    await websocket.send_json({
                                        "type": "error",
                                        "content": "消息内容不能为空"
                                    })
                                    continue
                                
                                # 生成响应
                                logger.info(f"处理文本消息: {text_content}")
                                response = await self.agent.process_text(text_content)
                                
                                # 发送文本响应
                                await websocket.send_json({
                                    "type": "text",
                                    "content": response
                                })
                                
                                # 检查是否需要生成语音
                                if json_data.get("need_audio", True):
                                    # 生成语音
                                    audio_response = await self.speech_processor.text_to_speech(response)
                                    audio_response_base64 = base64.b64encode(audio_response).decode('utf-8')
                                    
                                    # 发送音频响应
                                    await websocket.send_json({
                                        "type": "audio",
                                        "content": audio_response_base64
                                    })
                            else:
                                await websocket.send_json({
                                    "type": "error",
                                    "content": "无效的消息格式"
                                })
                    
                    except WebSocketDisconnect:
                        logger.info("WebSocket连接断开")
                        break
                    except json.JSONDecodeError:
                        logger.error("JSON解析错误")
                        await websocket.send_json({
                            "type": "error",
                            "content": "无效的JSON格式"
                        })
                    except Exception as e:
                        logger.error(f"处理WebSocket消息错误: {e}", exc_info=True)
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "content": "服务器处理请求时出错"
                            })
                        except:
                            # 如果连接已断开，忽略错误
                            break
            
            except WebSocketDisconnect:
                logger.info("WebSocket客户端断开连接")
            except Exception as e:
                logger.error(f"WebSocket处理错误: {e}", exc_info=True)
            finally:
                # 清理
                heartbeat_task.cancel()
                self.connection_manager.disconnect(websocket)
        
        @self.app.post("/upload-audio")
        async def upload_audio(file: UploadFile = File(...)):
            try:
                # 读取上传的音频文件
                audio_data = await file.read()
                
                if len(audio_data) > self.MAX_AUDIO_SIZE:
                    raise HTTPException(status_code=413, detail=f"文件太大，最大允许 {self.MAX_AUDIO_SIZE} bytes")
                
                # 语音转文字
                text = await self.speech_processor.speech_to_text(audio_data)
                if not text:
                    raise HTTPException(status_code=400, detail="无法识别音频内容")
                
                # 生成响应
                response = await self.agent.process_text(text)
                
                # 生成语音响应
                audio_response = await self.speech_processor.text_to_speech(response)
                
                # 返回结果
                return {
                    "recognized_text": text,
                    "response": response,
                    "audio_response": base64.b64encode(audio_response).decode('utf-8')
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"处理音频上传时出错: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")
    
    async def start(self):
        """启动服务器"""
        try:
            # 启动连接清理任务
            cleanup_task = asyncio.create_task(self.cleanup_connections_task())
            self.background_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(self.background_tasks.discard)
            
            ssl_config = SERVER_CONFIG['ssl']
            host = SERVER_CONFIG['host']
            port = SERVER_CONFIG['port']
            
            if ssl_config['enabled']:
                # 检查SSL证书文件
                key_file = ssl_config['key_file']
                cert_file = ssl_config['cert_file']
                
                if not key_file.exists() or not cert_file.exists():
                    logger.warning("SSL证书文件不存在，禁用SSL")
                    ssl_context = None
                else:
                    # 创建SSL上下文
                    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    ssl_context.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
                    logger.info(f"已加载SSL证书: {cert_file}")
            else:
                ssl_context = None
            
            # 配置服务器
            config = uvicorn.Config(
                app=self.app,
                host=host,
                port=port,
                ssl_certfile=str(ssl_config['cert_file']) if ssl_context else None,
                ssl_keyfile=str(ssl_config['key_file']) if ssl_context else None,
                log_level="info"
            )
            
            # 创建服务器
            server = uvicorn.Server(config)
            logger.info(f"服务器启动在 {'https' if ssl_context else 'http'}://{host}:{port}")
            
            # 启动服务器
            await server.serve()
            
        except Exception as e:
            logger.error(f"服务器启动出错: {e}", exc_info=True)
            raise
        finally:
            # 取消所有后台任务
            for task in self.background_tasks:
                task.cancel()
