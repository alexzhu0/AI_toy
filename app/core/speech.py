"""语音处理模块"""
import os
import json
import time
import base64
import hashlib
import hmac
import asyncio
import websocket
import edge_tts
import numpy as np
from datetime import datetime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from time import mktime
import logging
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)

class SpeechProcessor:
    def __init__(self):
        # Edge TTS 配置
        self.voice = os.getenv('EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural')
        
        # 讯飞 API 配置
        self.APPID = os.getenv("XUNFEI_APPID")
        self.APIKey = os.getenv("XUNFEI_APIKEY")
        self.APISecret = os.getenv("XUNFEI_APISECRET")
        
        # 讯飞 API URL
        self.HOST = "ws-api.xfyun.cn"
        self.ROUTE = "/v2/iat"
        
        if not all([self.APPID, self.APIKey, self.APISecret]):
            raise ValueError("请设置讯飞 API 的环境变量：XUNFEI_APPID, XUNFEI_APIKEY, XUNFEI_APISECRET")
        
        # 音频配置
        self.SAMPLE_RATE = 16000  # 采样率16k
        self.CHUNK_SIZE = 1280    # 每帧音频大小
        self.MAX_AUDIO_LENGTH = 60 # 最大音频长度（秒）
    
    def _create_url(self):
        """生成讯飞 API 的 URL"""
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        signature_origin = f"host: {self.HOST}\n"
        signature_origin += f"date: {date}\n"
        signature_origin += f"GET {self.ROUTE} HTTP/1.1"
        
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", '
        authorization_origin += f'headers="host date request-line", signature="{signature_sha_base64}"'
        
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.HOST
        }
        
        return f"wss://{self.HOST}{self.ROUTE}?{urlencode(params)}"
    
    async def text_to_speech(self, text: str) -> bytes:
        """将文本转换为语音"""
        communicate = edge_tts.Communicate(text, self.voice)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            temp_path = tmp_file.name
        
        try:
            await communicate.save(temp_path)
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            return audio_data
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """使用讯飞 API 进行语音识别"""
        try:
            print(f"收到音频数据长度: {len(audio_data)}字节")  # 调试日志
            if len(audio_data) == 0:
                print("错误：收到空音频数据")
                return ""

            # 增加音频数据校验
            if len(audio_data) > 10 * 1024 * 1024:  # 10MB
                print(f"音频数据过大: {len(audio_data)/1024/1024:.2f}MB")
                return "音频数据太大"
            
            if not audio_data:
                return "对不起，我没有听到声音。"
            
            # 将音频数据转换为PCM格式
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            if len(audio_np.shape) == 2:
                audio_np = audio_np.mean(axis=1).astype(np.int16)
            
            # 检查音频长度
            audio_length = len(audio_np) / self.SAMPLE_RATE
            if audio_length > self.MAX_AUDIO_LENGTH:
                return f"对不起，音频长度超过{self.MAX_AUDIO_LENGTH}秒限制。"
            
            # 确保音频数据是16位整数
            audio_np = np.clip(audio_np, -32768, 32767).astype(np.int16)
            
            # 重采样到16k（如果需要）
            if len(audio_np) / audio_length != self.SAMPLE_RATE:
                from scipy import signal
                audio_np = signal.resample(audio_np, int(len(audio_np) * self.SAMPLE_RATE / (len(audio_np) / audio_length)))
                audio_np = audio_np.astype(np.int16)
            
            # 确保音频数据长度是偶数
            if len(audio_np) % 2 != 0:
                audio_np = np.pad(audio_np, (0, 1), 'constant')
            
            # 创建事件循环
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = []
            recognition_complete = asyncio.Event()
            
            def on_message(ws, message):
                try:
                    message = json.loads(message)
                    code = message.get("code", -1)
                    
                    if code != 0:
                        logger.error(f"讯飞 API 错误: {message}")
                        loop.call_soon_threadsafe(recognition_complete.set)
                        return
                    
                    data = message["data"]
                    if "result" in data:
                        result_dict = data["result"]
                        if "ws" in result_dict:
                            temp_result = []
                            for ws_item in result_dict["ws"]:
                                if "cw" in ws_item:
                                    best_word = max(
                                        ws_item["cw"],
                                        key=lambda x: float(x.get("sc", 0))
                                    )
                                    if best_word["w"]:
                                        temp_result.append(best_word["w"])
                            
                            if temp_result:
                                result.clear()
                                result.extend(temp_result)
                            
                            if data["status"] == 2:  # 最终结果
                                loop.call_soon_threadsafe(recognition_complete.set)
                    
                except Exception as e:
                    logger.error(f"处理消息错误: {e}")
                    loop.call_soon_threadsafe(recognition_complete.set)
            
            def on_error(ws, error):
                logger.error(f"讯飞 API 错误: {error}")
                loop.call_soon_threadsafe(recognition_complete.set)
            
            def on_close(ws, close_status_code, close_msg):
                if not recognition_complete.is_set():
                    loop.call_soon_threadsafe(recognition_complete.set)
            
            def on_open(ws):
                def run(*args):
                    try:
                        status = 0        # 音频的状态
                        
                        # 确保音频数据长度是帧大小的整数倍
                        if len(audio_np) % self.CHUNK_SIZE != 0:
                            padding = self.CHUNK_SIZE - (len(audio_np) % self.CHUNK_SIZE)
                            audio_np_padded = np.pad(audio_np, (0, padding), 'constant')
                        else:
                            audio_np_padded = audio_np
                        
                        total_frames = len(audio_np_padded) // self.CHUNK_SIZE
                        
                        # 分帧发送音频
                        for i in range(0, len(audio_np_padded), self.CHUNK_SIZE):
                            if i+self.CHUNK_SIZE >= len(audio_np_padded):
                                status = 2  # 最后一帧音频
                            
                            frame = audio_np_padded[i:i+self.CHUNK_SIZE]
                            frame_bytes = frame.tobytes()
                            
                            data = {
                                "common": {
                                    "app_id": self.APPID
                                },
                                "business": {
                                    "language": "zh_cn",
                                    "domain": "iat",
                                    "accent": "mandarin",
                                    "vad_eos": 3000,
                                    "dwa": "wpgs",        # 开启动态修正功能
                                    "pd": "game",         # 游戏领域
                                    "ptt": 0,             # 不带标点
                                    "rlang": "zh-cn",     # 中文识别
                                    "vinfo": 1,           # 返回音频信息
                                    "nunum": 0,           # 规范数字格式
                                    "speex_size": 70      # 音频前端点检测
                                },
                                "data": {
                                    "status": status,
                                    "format": "audio/L16;rate=16000",
                                    "encoding": "raw",
                                    "audio": base64.b64encode(frame_bytes).decode('utf-8')
                                }
                            }
                            ws.send(json.dumps(data))
                            time.sleep(0.04)  # 40ms 发送间隔
                            
                    except Exception as e:
                        logger.error(f"发送数据错误: {e}")
                        loop.call_soon_threadsafe(recognition_complete.set)
                
                loop.call_soon_threadsafe(lambda: asyncio.run_coroutine_threadsafe(
                    asyncio.to_thread(run), loop))
            
            # 创建 WebSocket 连接
            ws = websocket.WebSocketApp(
                self._create_url(),
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # 在后台运行 WebSocket
            ws_future = asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(lambda: ws.run_forever(sslopt={"cert_reqs": 0})),
                loop
            )
            
            # 等待识别完成
            try:
                await asyncio.wait_for(recognition_complete.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                return "对不起，识别超时了。"
            finally:
                ws.close()
                try:
                    ws_future.cancel()
                except:
                    pass
            
            final_text = "".join(result)
            if not final_text:
                return "对不起，我没有听清楚。"
            
            return final_text
            
        except Exception as e:
            logger.error(f"语音识别错误: {e}")
            return "对不起，识别出错了。" 