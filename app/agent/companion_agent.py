"""AI伴侣代理模块"""
import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.memory import Memory
from app.core.state import StateManager
from app.core.speech import SpeechProcessor

logger = logging.getLogger(__name__)

class AgentState(BaseModel):
    """代理状态"""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    current_topic: Optional[str] = None
    emotional_state: Optional[str] = None

class CompanionAgent:
    def __init__(
        self,
        memory: Optional[Memory] = None,
        state_manager: Optional[StateManager] = None,
        speech_processor: Optional[SpeechProcessor] = None
    ):
        self.memory = memory
        self.state_manager = state_manager
        self.speech_processor = speech_processor
        
        # 初始化 OpenAI 客户端
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            logger.warning("没有找到DEEPSEEK_API_KEY环境变量，将无法使用AI功能")
            self.client = None
        else:    
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
                timeout=60.0  # 设置更长的超时时间
            )
        
        # 系统提示词
        self.system_prompt = """你是一个温暖、有趣的AI伴侣。你会用简短、温暖的中文回应用户。
        你的目标是提供情感支持、有趣的对话和有用的信息。
        你应该关注用户的兴趣和情绪状态，并据此调整回应。
        你的回答应该简洁明了，避免过长解释。"""
        
        # 对话历史
        self.messages: List[Dict[str, str]] = []
        
        # 网络错误重试配置
        self.max_retries = 3
        self.retry_delay = 1  # 初始延迟1秒
        
        logger.info("AI伴侣代理初始化完成")
    
    async def _call_api_with_retry(self, messages, temperature=0.7, max_tokens=2000):
        """带重试机制的API调用"""
        if not self.client:
            return "抱歉，AI服务暂时不可用。请确保DEEPSEEK_API_KEY环境变量已设置。"
            
        retries = 0
        delay = self.retry_delay
        
        while retries < self.max_retries:
            try:
                response = await self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                return response.choices[0].message.content
                
            except asyncio.TimeoutError:
                logger.warning(f"API调用超时，重试 {retries + 1}/{self.max_retries}")
                retries += 1
                if retries >= self.max_retries:
                    break
                await asyncio.sleep(delay)
                delay *= 2  # 指数退避策略
                
            except Exception as e:
                logger.error(f"API调用错误: {e}", exc_info=True)
                if "rate_limit" in str(e).lower():
                    # 速率限制错误，增加等待时间
                    logger.warning("遇到速率限制，等待更长时间")
                    retries += 1
                    if retries >= self.max_retries:
                        break
                    await asyncio.sleep(delay * 2)  # 速率限制时等待更长时间
                    delay *= 3  # 速率限制时使用更激进的退避策略
                else:
                    # 其他错误直接退出重试
                    break
                    
        return "对不起，我现在遇到了一些网络问题，能稍后再聊吗？"
    
    async def process_text(self, text: str) -> str:
        """处理文本输入并生成响应"""
        try:
            logger.info(f"收到用户输入: {text}")
            
            if not text or not text.strip():
                return "嗯？我没听清你说什么，能再说一遍吗？"
            
            # 准备消息
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # 添加历史消息 (限制5条以控制token用量)
            messages.extend(self.messages[-5:])
            
            # 添加用户输入
            messages.append({"role": "user", "content": text})
            
            # 调用API
            response = await self._call_api_with_retry(messages)
            logger.info(f"生成的响应: {response}")
            
            # 保存对话历史
            self.messages.append({"role": "user", "content": text})
            self.messages.append({"role": "assistant", "content": response})
            
            # 清理较旧的消息，避免内存泄漏
            if len(self.messages) > 100:
                self.messages = self.messages[-50:]  # 只保留最近50条
            
            # 更新状态
            if self.state_manager:
                try:
                    self.state_manager.update_last_interaction()
                    self.state_manager.add_to_history("user", text)
                    self.state_manager.add_to_history("assistant", response)
                except Exception as e:
                    logger.error(f"更新状态时出错: {e}", exc_info=True)
            
            # 保存到记忆
            if self.memory:
                try:
                    self.memory.add_memory(
                        memory_type="conversation",
                        content=text,
                        metadata={
                            "response": response,
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                except Exception as e:
                    logger.error(f"保存记忆时出错: {e}", exc_info=True)
            
            return response
            
        except Exception as e:
            logger.error(f"处理文本时出错: {e}", exc_info=True)
            return "对不起，我现在有点累了，能稍后再聊吗？"