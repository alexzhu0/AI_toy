"""命令行交互客户端"""
import asyncio
import edge_tts
import sounddevice as sd
import numpy as np
import soundfile as sf
import tempfile
import os
import signal
from app.core.speech import SpeechProcessor
from app.agent.companion_agent import CompanionAgent
from app.core.memory import Memory
from app.core.state import StateManager
from config.settings import USER_CONFIG
import logging
import sys
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cli.log"),
    ]
)
logger = logging.getLogger(__name__)

class CommandLineClient:
    def __init__(self):
        """初始化命令行客户端"""
        try:
            logger.info("正在初始化命令行客户端...")
            self.speech_processor = SpeechProcessor()
            self.memory = Memory()
            self.state_manager = StateManager(USER_CONFIG)
            self.agent = CompanionAgent(
                self.memory,
                self.state_manager,
                self.speech_processor
            )
            
            # 录音配置
            self.sample_rate = 16000
            self.channels = 1
            self.dtype = np.int16
            
            # 临时文件列表，用于清理
            self.temp_files = []
            
            # 设置信号处理
            signal.signal(signal.SIGINT, self._signal_handler)
            
            logger.info("命令行客户端初始化完成")
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            print("初始化失败，请检查日志了解详情。")
            sys.exit(1)
    
    def _signal_handler(self, sig, frame):
        """处理Ctrl+C信号"""
        print("\n正在清理资源并退出...")
        self._cleanup()
        sys.exit(0)
    
    def _cleanup(self):
        """清理临时文件"""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.error(f"删除临时文件错误: {e}")
    
    async def record_audio(self, duration=5):
        """录制音频"""
        print(f"\n开始录音（{duration}秒）...")
        
        try:
            # 录制音频
            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype
            )
            
            # 添加进度条显示
            for i in range(duration):
                print(f"录音中: {'■' * (i+1)}{'□' * (duration-i-1)} {i+1}/{duration}秒", end='\r')
                await asyncio.sleep(1)
            
            sd.wait()
            print("\n录音完成" + " " * 40)  # 清除进度条
            
            return audio_data.tobytes()
        except Exception as e:
            logger.error(f"录音错误: {e}", exc_info=True)
            print("录音失败，请检查麦克风设置")
            return None
    
    async def play_audio(self, audio_data):
        """播放音频"""
        if not audio_data:
            logger.error("尝试播放空音频数据")
            return
            
        temp_path = None
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                temp_path = tmp_file.name
                self.temp_files.append(temp_path)
            
            # 写入音频数据
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # 读取并播放音频
            data, sample_rate = sf.read(temp_path)
            sd.play(data, sample_rate)
            sd.wait()
            
        except Exception as e:
            logger.error(f"播放音频错误: {e}", exc_info=True)
            print("播放音频失败")
        finally:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    self.temp_files.remove(temp_path)
                except:
                    pass
    
    async def conversation_loop(self):
        """对话循环"""
        print("\n欢迎使用AI助手！")
        print("-------------------")
        print("按Ctrl+C退出")
        print("-------------------")
        
        while True:
            try:
                print("\n请选择模式:")
                print("1. 语音对话")
                print("2. 文字对话")
                print("3. 退出程序")
                
                choice = input("\n请输入选项 (1/2/3): ").strip()
                
                if choice == "1":
                    # 语音对话模式
                    duration = 5
                    try:
                        custom_duration = input("录音时长(秒)，默认5秒。按回车使用默认值: ").strip()
                        if custom_duration:
                            duration = int(custom_duration)
                    except ValueError:
                        print("输入无效，使用默认值5秒")
                        duration = 5
                    
                    audio_data = await self.record_audio(duration)
                    if not audio_data:
                        continue
                    
                    print("正在识别语音...")
                    start_time = time.time()
                    text = await self.speech_processor.speech_to_text(audio_data)
                    logger.info(f"语音识别耗时: {time.time() - start_time:.2f}秒")
                    
                    if text and not text.lower().startswith("对不起"):
                        print(f"识别结果: {text}")
                        
                        print("正在生成回复...")
                        start_time = time.time()
                        response = await self.agent.process_text(text)
                        logger.info(f"生成回复耗时: {time.time() - start_time:.2f}秒")
                        print(f"AI回复: {response}")
                        
                        print("正在生成语音...")
                        start_time = time.time()
                        audio_response = await self.speech_processor.text_to_speech(response)
                        logger.info(f"语音合成耗时: {time.time() - start_time:.2f}秒")
                        
                        print("播放回复...")
                        await self.play_audio(audio_response)
                    else:
                        print("语音识别失败或未检测到语音，请重试")
                
                elif choice == "2":
                    # 文字对话模式
                    text = input("\n请输入消息: ").strip()
                    if not text:
                        continue
                    
                    print("正在生成回复...")
                    start_time = time.time()
                    response = await self.agent.process_text(text)
                    logger.info(f"生成回复耗时: {time.time() - start_time:.2f}秒")
                    print(f"AI回复: {response}")
                    
                    # 询问是否需要播放语音
                    play_audio = input("是否播放语音回复? (y/n): ").strip().lower()
                    if play_audio in ('y', 'yes', '是'):
                        print("正在生成语音...")
                        start_time = time.time()
                        audio_response = await self.speech_processor.text_to_speech(response)
                        logger.info(f"语音合成耗时: {time.time() - start_time:.2f}秒")
                        
                        print("播放回复...")
                        await self.play_audio(audio_response)
                
                elif choice == "3":
                    print("\n感谢使用，再见！")
                    break
                
                else:
                    print("无效的选择，请输入1、2或3")
            
            except KeyboardInterrupt:
                print("\n\n感谢使用，再见！")
                break
            except Exception as e:
                logger.error(f"错误: {e}", exc_info=True)
                print(f"发生错误: {e}")
                print("正在重置对话状态...")
                await asyncio.sleep(1)

async def main():
    try:
        client = CommandLineClient()
        await client.conversation_loop()
    except Exception as e:
        logger.critical(f"程序崩溃: {e}", exc_info=True)
        print(f"程序崩溃: {e}")
    finally:
        print("正在清理资源...")

if __name__ == "__main__":
    asyncio.run(main())
