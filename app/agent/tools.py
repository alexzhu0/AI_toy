"""工具模块"""
from langchain.tools import Tool, BaseTool
from typing import Optional, List, Dict, Any, Type, Annotated
from datetime import datetime
import json
from pydantic import BaseModel, Field

class MemoryInput(BaseModel):
    """获取记忆的输入参数"""
    limit: Annotated[int, Field(description="获取记忆的数量限制", ge=1, le=100)] = 5

class AddMemoryInput(BaseModel):
    """添加记忆的输入参数"""
    content: Annotated[str, Field(description="记忆内容", min_length=1)]
    memory_type: Annotated[str, Field(description="记忆类型")] = "conversation"
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")

class StateInput(BaseModel):
    """情感状态输入参数"""
    state: Annotated[str, Field(description="情感状态", min_length=1)]

class TopicInput(BaseModel):
    """话题输入参数"""
    topic: Annotated[str, Field(description="当前话题", min_length=1)]

class SpeechInput(BaseModel):
    """语音转换输入参数"""
    text: Annotated[str, Field(description="要转换的文本", min_length=1)]

class AudioInput(BaseModel):
    """音频识别输入参数"""
    audio_data: Annotated[bytes, Field(description="要识别的音频数据")]

class MemoryCountInput(BaseModel):
    """记忆数量输入参数"""
    count: Annotated[int, Field(description="获取记忆的数量", ge=1, le=100)]

class EmotionalStateInput(BaseModel):
    """情感状态输入参数"""
    emotion: Annotated[str, Field(description="情感状态", min_length=1)]
    intensity: Annotated[float, Field(description="情感强度", ge=0.0, le=1.0)]

def create_memory_tools(memory) -> List[Tool]:
    """创建记忆相关的工具"""
    def get_recent_memories(memory_input: MemoryCountInput) -> str:
        """获取最近的记忆"""
        raise NotImplementedError("请使用异步版本")

    def add_memory(memory_input: AddMemoryInput) -> str:
        """添加新的记忆"""
        raise NotImplementedError("请使用异步版本")

    async def async_get_recent_memories(memory_input: MemoryCountInput) -> str:
        """异步获取最近的记忆"""
        try:
            memories = await memory.get_recent_memories(memory_input.count)
            if not memories:
                return "没有找到任何记忆"
            return "\n".join([f"{m.time}: {m.content}" for m in memories])
        except Exception as e:
            print(f"获取记忆错误: {e}")
            return "获取记忆时发生错误"

    async def async_add_memory(memory_input: AddMemoryInput) -> str:
        """异步添加新的记忆"""
        try:
            await memory.add_memory(
                content=memory_input.content,
                memory_type=memory_input.memory_type,
                metadata=memory_input.metadata
            )
            return "记忆已保存"
        except Exception as e:
            print(f"添加记忆错误: {e}")
            return "保存记忆时发生错误"

    return [
        Tool(
            name="get_recent_memories",
            description="获取最近的记忆，可以指定获取数量",
            func=get_recent_memories,
            coroutine=async_get_recent_memories,
            args_schema=MemoryCountInput,
            return_direct=True
        ),
        Tool(
            name="add_memory",
            description="添加新的记忆",
            func=add_memory,
            coroutine=async_add_memory,
            args_schema=AddMemoryInput,
            return_direct=True
        )
    ]

def create_state_tools(state_manager) -> List[Tool]:
    """创建状态相关的工具"""
    def update_emotional_state(state_input: EmotionalStateInput) -> str:
        """更新情感状态"""
        raise NotImplementedError("请使用异步版本")

    def update_topic(topic_input: TopicInput) -> str:
        """更新当前话题"""
        raise NotImplementedError("请使用异步版本")

    def get_user_info() -> str:
        """获取用户信息"""
        raise NotImplementedError("请使用异步版本")

    async def async_update_emotional_state(state_input: EmotionalStateInput) -> str:
        """异步更新情感状态"""
        try:
            await state_manager.update_emotional_state(state_input.emotion, state_input.intensity)
            return f"情感状态已更新为 {state_input.emotion}，强度为 {state_input.intensity}"
        except Exception as e:
            print(f"更新情感状态错误: {e}")
            return "更新情感状态时发生错误"

    async def async_update_topic(topic_input: TopicInput) -> str:
        """异步更新当前话题"""
        try:
            await state_manager.update_topic(topic_input.topic)
            return f"当前话题已更新为: {topic_input.topic}"
        except Exception as e:
            print(f"更新话题错误: {e}")
            return "更新话题时发生错误"

    async def async_get_user_info() -> str:
        """异步获取用户信息"""
        try:
            user_info = await state_manager.get_user_info()
            if not user_info:
                return "没有获取到用户信息"
            return str(user_info)
        except Exception as e:
            print(f"获取用户信息错误: {e}")
            return "获取用户信息时发生错误"

    return [
        Tool(
            name="update_emotional_state",
            description="更新AI助手的情感状态",
            func=update_emotional_state,
            coroutine=async_update_emotional_state,
            args_schema=EmotionalStateInput,
            return_direct=True
        ),
        Tool(
            name="update_topic",
            description="更新当前对话的话题",
            func=update_topic,
            coroutine=async_update_topic,
            args_schema=TopicInput,
            return_direct=True
        ),
        Tool(
            name="get_user_info",
            description="获取用户的基本信息",
            func=get_user_info,
            coroutine=async_get_user_info,
            args_schema=None,
            return_direct=True
        )
    ]

def create_speech_tools(speech_processor) -> List[Tool]:
    """创建语音处理相关的工具"""
    def text_to_speech(speech_input: SpeechInput) -> bytes:
        """文本转语音"""
        raise NotImplementedError("请使用异步版本")

    def speech_to_text(audio_input: AudioInput) -> str:
        """语音转文本"""
        raise NotImplementedError("请使用异步版本")

    async def async_text_to_speech(speech_input: SpeechInput) -> bytes:
        """异步文本转语音"""
        try:
            if not speech_input.text:
                raise ValueError("文本为空")
            return await speech_processor.text_to_speech(speech_input.text)
        except Exception as e:
            print(f"文本转语音错误: {e}")
            raise

    async def async_speech_to_text(audio_input: AudioInput) -> str:
        """异步语音转文本"""
        try:
            if not audio_input.audio_data:
                raise ValueError("音频数据为空")
            text = await speech_processor.speech_to_text(audio_input.audio_data)
            if not text:
                return "没有识别出语音内容"
            return text
        except Exception as e:
            print(f"语音转文本错误: {e}")
            raise

    return [
        Tool(
            name="text_to_speech",
            description="将文本转换为语音，返回音频数据",
            func=text_to_speech,
            coroutine=async_text_to_speech,
            args_schema=SpeechInput,
            return_direct=True
        ),
        Tool(
            name="speech_to_text",
            description="将语音转换为文本，需要提供音频数据",
            func=speech_to_text,
            coroutine=async_speech_to_text,
            args_schema=AudioInput,
            return_direct=True
        )
    ]

def get_all_tools(memory_system, state_manager, speech_processor) -> List[Tool]:
    """获取所有可用工具"""
    tools = []
    tools.extend(create_memory_tools(memory_system))
    tools.extend(create_state_tools(state_manager))
    tools.extend(create_speech_tools(speech_processor))
    return tools 