"""语音处理模块"""
import os
import json
import time
import base64
import hashlib
import hmac
import asyncio
import websockets
import edge_tts
import numpy as np
import soundfile as sf
import io
from scipy import signal
from datetime import datetime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from time import mktime
import logging
from typing import Optional, Tuple, Dict, Any
import tempfile
import ssl

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # 添加控制台处理程序
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    
    # 创建格式化程序
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    
    # 添加处理程序到logger
    logger.addHandler(ch)

class SpeechProcessor:
    def __init__(self):
        """初始化语音处理器"""
        # Edge TTS 配置
        self.voice = os.getenv('EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural')
        logger.info(f"使用语音模型: {self.voice}")
        
        # 讯飞 API 配置
        self.APPID = os.getenv("XUNFEI_APPID")
        self.APIKey = os.getenv("XUNFEI_APIKEY")
        self.APISecret = os.getenv("XUNFEI_APISECRET")
        
        # 验证API配置
        if not all([self.APPID, self.APIKey, self.APISecret]):
            raise ValueError("请设置讯飞 API 的环境变量：XUNFEI_APPID, XUNFEI_APIKEY, XUNFEI_APISECRET")
        
        # 讯飞 API URL
        self.HOST = "ws-api.xfyun.cn"
        self.ROUTE = "/v2/iat"
        
        # 音频配置
        self.SAMPLE_RATE = 16000  # 采样率16k
        self.CHUNK_SIZE = 1280    # 每帧音频大小
        self.MAX_AUDIO_LENGTH = 60 # 最大音频长度（秒）
        
        logger.info("语音处理器初始化完成")
    
    def _create_url(self) -> str:
        """生成讯飞 API 的 URL"""
        try:
            # 生成时间戳
            now = datetime.now()
            date = format_date_time(mktime(now.timetuple()))
            
            # 生成签名原文
            signature_origin = f"host: {self.HOST}\n"
            signature_origin += f"date: {date}\n"
            signature_origin += f"GET {self.ROUTE} HTTP/1.1"
            
            # 计算签名
            signature_sha = hmac.new(
                self.APISecret.encode('utf-8'),
                signature_origin.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            
            signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
            
            # 生成授权信息
            authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", '
            authorization_origin += f'headers="host date request-line", signature="{signature_sha_base64}"'
            
            authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
            
            # 生成URL参数
            params = {
                "authorization": authorization,
                "date": date,
                "host": self.HOST
            }
            
            url = f"wss://{self.HOST}{self.ROUTE}?{urlencode(params)}"
            logger.debug(f"生成WebSocket URL: {url}")
            return url
            
        except Exception as e:
            logger.error(f"生成URL错误: {e}", exc_info=True)
            raise
    
    def _prepare_audio_frames(self, audio_np: np.ndarray) -> list:
        """准备音频帧数据"""
        try:
            # 确保音频数据长度是帧大小的整数倍
            if len(audio_np) % self.CHUNK_SIZE != 0:
                padding_size = self.CHUNK_SIZE - (len(audio_np) % self.CHUNK_SIZE)
                audio_np = np.pad(audio_np, (0, padding_size), 'constant')
            
            # 将音频数据分割成帧
            frames = []
            total_frames = len(audio_np) // self.CHUNK_SIZE
            
            for i in range(0, len(audio_np), self.CHUNK_SIZE):
                frame = audio_np[i:i+self.CHUNK_SIZE]
                status = 0  # 中间帧
                
                if i == 0:
                    status = 1  # 第一帧
                elif i + self.CHUNK_SIZE >= len(audio_np):
                    status = 2  # 最后一帧
                
                frame_data = {
                    "data": base64.b64encode(frame.tobytes()).decode('utf-8'),
                    "status": status
                }
                frames.append(frame_data)
            
            logger.debug(f"音频分帧完成，共{len(frames)}帧")
            return frames
            
        except Exception as e:
            logger.error(f"音频帧准备错误: {e}", exc_info=True)
            raise
    
    async def _send_audio_frames(self, ws, frames: list):
        """发送音频帧数据"""
        try:
            for i, frame in enumerate(frames):
                data = {
                    "common": {"app_id": self.APPID},
                    "business": {
                        "language": "zh_cn",
                        "domain": "iat",
                        "accent": "mandarin",
                        "dwa": "wpgs",  # 开启实时识别结果返回
                        "pd": "game",
                        "ptt": 0,  # 标点符号过滤
                        "rlang": "zh-cn",
                        "vinfo": 1,
                        "vad_eos": 10000,  # 最大静音检测时长
                        "nunum": 0,  # 数字以汉字形式输出
                        "speex_size": 70,  # speex音频帧大小
                        "nbest": 3,  # 返回多候选结果
                        "wbest": 5   # 词级多候选
                    },
                    "data": {
                        "status": frame["status"],
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": frame["data"]
                    }
                }
                
                await ws.send(json.dumps(data))
                logger.debug(f"发送第{i+1}/{len(frames)}帧")
                await asyncio.sleep(0.04)  # 控制发送速率
                
        except Exception as e:
            logger.error(f"发送音频帧错误: {e}", exc_info=True)
            raise
    
    async def _handle_websocket_messages(self, ws, result: list, complete: asyncio.Event):
        """处理WebSocket消息"""
        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    logger.debug(f"收到消息: {data}")
                    
                    code = data.get("code", -1)
                    if code != 0:
                        error_desc = data.get('desc', '未知错误')
                        logger.error(f"讯飞 API 错误: {error_desc}")
                        complete.set()
                        return
                    
                    if "data" in data:
                        text = self._extract_text_from_response(data["data"])
                        if text:
                            result.append(text)
                            logger.debug(f"识别文本: {text}")
                        
                        if data["data"].get("status", 0) == 2:
                            logger.info("语音识别完成")
                            complete.set()
                            
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析错误: {e}")
                except Exception as e:
                    logger.error(f"处理消息错误: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"WebSocket消息处理错误: {e}", exc_info=True)
            complete.set()
    
    def _extract_text_from_response(self, data: Dict[str, Any]) -> str:
        """从响应中提取文本"""
        try:
            if "result" not in data:
                return ""
                
            result = data["result"]
            if not isinstance(result, dict) or "ws" not in result:
                return ""
            
            text = ""
            for ws_item in result["ws"]:
                if "cw" not in ws_item:
                    continue
                    
                # 获取所有候选词及其置信度
                candidates = [(w["w"], float(w.get("sc", 0))) for w in ws_item["cw"]]
                
                # 选择置信度最高的词
                if candidates:
                    best_word = max(candidates, key=lambda x: x[1])
                    text += best_word[0]
            
            return text
            
        except Exception as e:
            logger.error(f"提取文本错误: {e}", exc_info=True)
            return ""
    
    async def text_to_speech(self, text: str) -> bytes:
        """将文本转换为语音"""
        if not text:
            logger.error("输入文本为空")
            raise ValueError("请提供要转换的文本")
        
        logger.info(f"开始文本转语音，文本: {text}")
        temp_path = None
        
        try:
            # 创建 Edge TTS 通信对象
            communicate = edge_tts.Communicate(text, self.voice)
            logger.debug(f"使用语音模型: {self.voice}")
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_path = tmp_file.name
                logger.debug(f"创建临时文件: {temp_path}")
            
            try:
                # 生成语音
                await communicate.save(temp_path)
                logger.info("语音合成完成")
                
                # 读取生成的音频数据
                with open(temp_path, 'rb') as f:
                    audio_data = f.read()
                logger.debug(f"读取的音频数据长度: {len(audio_data)} 字节")
                
                return audio_data
                
            except Exception as e:
                logger.error(f"语音合成错误: {e}", exc_info=True)
                raise
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    logger.debug(f"删除临时文件: {temp_path}")
                    
        except Exception as e:
            logger.error(f"文本转语音错误: {e}", exc_info=True)
            raise
    
    def _process_audio(self, audio_data: bytes) -> Tuple[np.ndarray, float]:
        """处理音频数据，确保正确的格式和采样率"""
        try:
            logger.info(f"开始处理音频数据，长度: {len(audio_data)} 字节")
            
            # 检查数据是否为WAV格式
            if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
                logger.info("检测到WAV格式音频")
                with io.BytesIO(audio_data) as audio_io:
                    try:
                        data, sample_rate = sf.read(audio_io)
                        logger.info(f"原始音频采样率: {sample_rate}Hz, 形状: {data.shape}")
                    except Exception as e:
                        logger.error(f"WAV文件读取失败: {e}")
                        raise ValueError("无效的WAV文件格式")
            else:
                logger.info("尝试解析为PCM格式")
                # 确保数据长度是偶数（16位采样要求）
                if len(audio_data) % 2 != 0:
                    logger.debug("裁剪音频数据以确保长度为偶数")
                    audio_data = audio_data[:-1]
                data = np.frombuffer(audio_data, dtype=np.int16)
                sample_rate = self.SAMPLE_RATE
                logger.info(f"将数据解析为PCM格式，长度: {len(data)}")

            # 确保数据不为空
            if len(data) == 0:
                logger.error("音频数据为空")
                raise ValueError("空的音频数据")

            # 确保是单声道
            if len(data.shape) == 2:
                logger.debug(f"将{data.shape[1]}声道音频转换为单声道")
                data = data.mean(axis=1)
            
            # 检查数据是否有效
            if np.all(data == 0):
                logger.error("音频数据全为0")
                raise ValueError("无效的音频数据：信号全为0")
            
            if not np.isfinite(data).all():
                logger.error("音频数据包含无效值")
                raise ValueError("无效的音频数据：包含NaN或Inf")
            
            # 转换为float32进行处理
            data = data.astype(np.float32) / 32768.0
            logger.debug(f"将数据转换为float32，范围: [{np.min(data)}, {np.max(data)}]")
            
            # 重采样到目标采样率
            if sample_rate != self.SAMPLE_RATE:
                logger.info(f"正在进行采样率转换: {sample_rate}Hz -> {self.SAMPLE_RATE}Hz")
                samples = int(len(data) * self.SAMPLE_RATE / sample_rate)
                data = signal.resample(data, samples)
                logger.debug(f"重采样后的数据长度: {len(data)}")
            
            # 应用预加重滤波器
            preemph = 0.97
            data = np.append(data[0], data[1:] - preemph * data[:-1])
            
            # 标准化音量
            max_amp = np.max(np.abs(data))
            if max_amp > 0:
                logger.debug(f"标准化音量，原始最大振幅: {max_amp}")
                data = data / max_amp
            else:
                logger.warning("音频信号过弱")
                raise ValueError("音频信号过弱")
            
            # 应用噪声门限
            noise_gate = 0.01  # -40dB
            data[np.abs(data) < noise_gate] = 0
            
            # 检查信噪比
            signal_power = np.mean(data ** 2)
            if signal_power < 1e-6:  # -60dB
                logger.warning("音频信号过弱或可能是噪音")
                raise ValueError("音频信号过弱或可能是噪音")
            
            # 转换回16位整数
            data = np.clip(data * 32767, -32768, 32767).astype(np.int16)
            logger.debug(f"转换为16位整数，范围: [{np.min(data)}, {np.max(data)}]")
            
            # 确保数据长度是CHUNK_SIZE的整数倍
            remainder = len(data) % self.CHUNK_SIZE
            if remainder != 0:
                padding_size = self.CHUNK_SIZE - remainder
                logger.debug(f"添加{padding_size}字节的填充以匹配帧大小")
                data = np.pad(data, (0, padding_size), mode='edge')  # 使用边缘填充而不是零填充
            
            audio_length = len(data) / self.SAMPLE_RATE
            logger.info(f"音频处理完成，长度: {len(data)}采样点 ({audio_length:.2f}秒)")
            return data, audio_length
            
        except Exception as e:
            logger.error(f"音频处理错误: {e}", exc_info=True)
            raise

    async def speech_to_text(self, audio_data: bytes) -> str:
        """使用讯飞 API 进行语音识别"""
        try:
            # 验证音频数据
            if not audio_data:
                logger.error("音频数据为空")
                return "请提供音频数据"
            
            logger.info(f"开始处理音频数据，长度: {len(audio_data)} 字节")
            
            # 处理音频数据
            try:
                audio_np, audio_length = await asyncio.to_thread(self._process_audio, audio_data)
                logger.info(f"音频处理完成，时长: {audio_length:.2f} 秒")
            except ValueError as e:
                logger.error(f"音频处理错误: {e}", exc_info=True)
                return str(e)
            except Exception as e:
                logger.error(f"音频处理错误: {e}", exc_info=True)
                return "音频处理失败，请确保使用正确的音频格式和合适的音量"
            
            # 检查音频长度
            if audio_length < 0.5:  # 音频太短
                logger.warning(f"音频太短: {audio_length:.2f} 秒")
                return "音频太短，请说话时间长一点"
            
            if audio_length > self.MAX_AUDIO_LENGTH:
                logger.warning(f"音频超过长度限制: {audio_length:.2f} > {self.MAX_AUDIO_LENGTH}")
                return f"请将音频控制在 {self.MAX_AUDIO_LENGTH} 秒以内"
            
            # 准备WebSocket连接
            url = self._create_url()
            logger.debug(f"WebSocket URL: {url}")
            
            # 初始化结果存储
            recognition_result = []
            recognition_complete = asyncio.Event()
            
            # 准备音频数据
            frames = self._prepare_audio_frames(audio_np)
            
            try:
                async with websockets.connect(url, ssl=ssl._create_unverified_context()) as ws:
                    logger.info("已连接到讯飞 API WebSocket")
                    
                    # 启动接收线程
                    receive_task = asyncio.create_task(
                        self._handle_websocket_messages(ws, recognition_result, recognition_complete)
                    )
                    
                    # 发送音频数据
                    await self._send_audio_frames(ws, frames)
                    
                    # 等待识别完成
                    try:
                        await asyncio.wait_for(recognition_complete.wait(), timeout=10.0)
                        logger.info("语音识别完成")
                    except asyncio.TimeoutError:
                        logger.error("语音识别超时")
                        return "语音识别超时，请重试"
                    finally:
                        receive_task.cancel()
                
                # 处理识别结果
                final_text = "".join(recognition_result)
                if not final_text:
                    logger.warning("没有识别出文字")
                    return "没有识别出文字，请说话大声一点或靠近麦克风"
                
                # 检查文本质量
                if len(final_text) < 2:
                    logger.warning(f"识别文字太短: {final_text}")
                    return "识别结果太短，请说话大声一点或说完整的句子"
                
                logger.info(f"语音识别结果: {final_text}")
                return final_text
                
            except Exception as e:
                logger.error(f"WebSocket连接错误: {e}", exc_info=True)
                return "语音识别服务连接失败"
                
        except Exception as e:
            logger.error(f"语音识别过程发生错误: {e}", exc_info=True)
            return "语音识别出错，请重试"
            
            def on_message(ws, message):
                try:
                    message = json.loads(message)
                    logger.debug(f"收到WebSocket消息: {message}")
                    code = message.get("code", -1)
                    
                    if code != 0:
                        error_desc = message.get('desc', '未知错误')
                        logger.error(f"讯飞 API 错误: {error_desc} 完整响应: {message}")
                        loop.call_soon_threadsafe(lambda: recognition_complete.set())
                        return
                    
                    data = message["data"]
                    if "result" in data:
                        result_dict = data["result"]
                        if "ws" in result_dict:
                            current_segment = []
                            for ws_item in result_dict["ws"]:
                                if "cw" in ws_item:
                                    # 获取所有候选词及其置信度
                                    candidates = [(w["w"], float(w.get("sc", 0))) for w in ws_item["cw"]]
                                    logger.debug(f"候选词: {candidates}")
                                    
                                    # 选择置信度最高的词
                                    best_word = max(candidates, key=lambda x: x[1])
                                    if best_word[0]:
                                        current_segment.append(best_word[0])
                                        logger.debug(f"选择词: {best_word[0]} (置信度: {best_word[1]})")
                            
                            if current_segment:
                                # 根据状态决定如何更新结果
                                if data["status"] == 0:  # 中间结果
                                    result.extend(current_segment)
                                elif data["status"] == 1:  # 部分结果
                                    # 更新最后一个句子
                                    result.extend(current_segment)
                                elif data["status"] == 2:  # 最终结果
                                    result.extend(current_segment)
                                    final_text = ''.join(result)
                                    logger.info(f"最终识别结果: {final_text}")
                                    loop.call_soon_threadsafe(lambda: recognition_complete.set())
                
                except Exception as e:
                    logger.error(f"处理消息错误: {e}\n原始消息: {message}", exc_info=True)
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
                        logger.debug(f"开始发送音频数据，总帧数: {total_frames}")
                        
                        for i in range(0, len(audio_np_padded), self.CHUNK_SIZE):
                            if i+self.CHUNK_SIZE >= len(audio_np_padded):
                                status = 2  # 最后一帧音频
                            
                            frame = audio_np_padded[i:i+self.CHUNK_SIZE]
                            frame_bytes = frame.tobytes()
                            
                            # 记录发送进度
                            if i % (10 * self.CHUNK_SIZE) == 0:  # 每10帧记录一次
                                logger.debug(f"已发送 {i//self.CHUNK_SIZE}/{total_frames} 帧")
                            
                            data = {
                                "common": {
                                    "app_id": self.APPID
                                },
                                "business": {
                                    "language": "zh_cn",
                                    "domain": "iat",
                                    "accent": "mandarin",
                                    "vad_eos": 3000,
                                    "dwa": "wpgs",
                                    "pd": "game",
                                    "ptt": 0,
                                    "rlang": "zh-cn",
                                    "vinfo": 1,
                                    "nunum": 0,
                                    "speex_size": 70
                                },
                                "data": {
                                    "status": status,
                                    "format": "audio/L16;rate=16000",
                                    "encoding": "raw",
                                    "audio": base64.b64encode(frame_bytes).decode('utf-8')
                                }
                            }
                            try:
                                ws.send(json.dumps(data))
                                time.sleep(0.06)  # 调整为60ms发送间隔
                            except Exception as send_error:
                                logger.error(f"发送音频帧失败: {send_error}")
                                loop.call_soon_threadsafe(recognition_complete.set)
                                break
                    
                    except Exception as e:
                        logger.error(f"发送数据错误: {e}")
                        loop.call_soon_threadsafe(recognition_complete.set)
                
                loop.call_soon_threadsafe(lambda: asyncio.run_coroutine_threadsafe(
                    asyncio.to_thread(run), loop))
            
            # 创建 WebSocket 连接
            logger.info("开始创建 WebSocket 连接")
            url = self._create_url()
            logger.debug(f"WebSocket URL: {url}")
            
            ws = websocket.WebSocketApp(
                url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # 配置SSL选项
            ssl_opts = {
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False
            }
            
            # 在后台运行 WebSocket
            logger.info("启动WebSocket连接")
            ws_future = asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(lambda: ws.run_forever(sslopt=ssl_opts)),
                loop
            )
            
            # 等待识别完成
            try:
                logger.info("等待语音识别完成")
                await asyncio.wait_for(recognition_complete.wait(), timeout=30.0)
                logger.info("语音识别完成")
            except asyncio.TimeoutError:
                logger.error("语音识别超时")
                return "对不起，识别超时了。"
            finally:
                logger.info("关闭WebSocket连接")
                ws.close()
                try:
                    ws_future.cancel()
                except Exception as e:
                    logger.error(f"取消WebSocket任务失败: {e}")
            
            final_text = "".join(result)
            if not final_text:
                logger.warning("语音识别结果为空")
                return "对不起，我没有听清楚。"
            
            logger.info(f"语音识别结果: {final_text}")
            return final_text
            
        except Exception as e:
            logger.error(f"语音识别错误: {e}")
            return "对不起，识别出错了。" 