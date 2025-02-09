"""代理和工具的测试模块"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from app.core.memory import Memory
from app.core.state import StateManager
from app.core.speech import SpeechProcessor
from app.agent.companion_agent import CompanionAgent
from app.agent.tools import (
    MemoryInput,
    AddMemoryInput,
    StateInput,
    TopicInput,
    SpeechInput,
    AudioInput,
    GetRecentMemoriesTool,
    AddMemoryTool,
    UpdateEmotionalStateTool,
    UpdateTopicTool,
    GetUserInfoTool,
    TextToSpeechTool,
    SpeechToTextTool
)

@pytest.fixture
def state_manager_mock():
    """创建状态管理器的 Mock 对象"""
    state = Mock(spec=StateManager)
    user_state = Mock()
    user_state.name = "小明"
    user_state.age = 8
    user_state.gender = "男"
    user_state.personality = "活泼"
    user_state.social = "喜欢交朋友"
    state.user_state = user_state
    return state

@pytest.fixture
def memory_mock():
    """创建记忆系统的 Mock 对象"""
    memory = Mock(spec=Memory)
    memory.get_recent_memories.return_value = [
        {
            "id": 1,
            "timestamp": datetime.now().isoformat(),
            "type": "conversation",
            "content": "测试内容",
            "metadata": None
        }
    ]
    return memory

@pytest.fixture
def speech_processor_mock():
    """创建语音处理器的 Mock 对象"""
    speech = AsyncMock(spec=SpeechProcessor)
    speech.text_to_speech.return_value = b"audio_data"
    speech.speech_to_text.return_value = "语音转文本结果"
    return speech

@pytest.fixture
def agent_mock(memory_mock, state_manager_mock, speech_processor_mock):
    """创建代理的 Mock 对象"""
    agent = CompanionAgent(memory_mock, state_manager_mock, speech_processor_mock)
    
    # 创建一个新的 Mock 对象来替换整个 agent_executor
    executor_mock = AsyncMock()
    executor_mock.ainvoke = AsyncMock(return_value={
        "output": "你好！我是小美。",
        "intermediate_steps": []
    })
    agent.agent_executor = executor_mock
    
    return agent

@pytest.mark.asyncio
async def test_get_recent_memories_tool(memory_mock):
    """测试获取记忆工具"""
    tool = GetRecentMemoriesTool(memory_mock)
    args = MemoryInput(limit=5)
    
    # 测试同步调用
    result = tool._run(args)
    assert len(result) == 1
    assert result[0]["content"] == "测试内容"
    
    # 测试异步调用
    result = await tool._arun(args)
    assert len(result) == 1
    assert result[0]["content"] == "测试内容"

@pytest.mark.asyncio
async def test_add_memory_tool(memory_mock):
    """测试添加记忆工具"""
    tool = AddMemoryTool(memory_mock)
    args = AddMemoryInput(
        content="新记忆",
        memory_type="conversation",
        metadata={"test": True}
    )
    
    # 测试同步调用
    result = tool._run(args)
    assert result == "记忆已添加"
    memory_mock.add_memory.assert_called_once_with(
        "conversation",
        "新记忆",
        {"test": True}
    )
    
    # 测试异步调用
    memory_mock.reset_mock()
    result = await tool._arun(args)
    assert result == "记忆已添加"
    memory_mock.add_memory.assert_called_once_with(
        "conversation",
        "新记忆",
        {"test": True}
    )

@pytest.mark.asyncio
async def test_update_emotional_state_tool(state_manager_mock):
    """测试更新情感状态工具"""
    tool = UpdateEmotionalStateTool(state_manager_mock)
    args = StateInput(state="开心")
    
    result = tool._run(args)
    assert result == "情感状态已更新为: 开心"
    state_manager_mock.set_emotional_state.assert_called_once_with("开心")
    
    state_manager_mock.reset_mock()
    result = await tool._arun(args)
    assert result == "情感状态已更新为: 开心"
    state_manager_mock.set_emotional_state.assert_called_once_with("开心")

@pytest.mark.asyncio
async def test_update_topic_tool(state_manager_mock):
    """测试更新话题工具"""
    tool = UpdateTopicTool(state_manager_mock)
    args = TopicInput(topic="学习")
    
    result = tool._run(args)
    assert result == "当前话题已更新为: 学习"
    state_manager_mock.set_current_topic.assert_called_once_with("学习")
    
    state_manager_mock.reset_mock()
    result = await tool._arun(args)
    assert result == "当前话题已更新为: 学习"
    state_manager_mock.set_current_topic.assert_called_once_with("学习")

def test_get_user_info_tool(state_manager_mock):
    """测试获取用户信息工具"""
    tool = GetUserInfoTool(state_manager_mock)
    
    result = tool._run()
    assert result["name"] == "小明"
    assert result["age"] == 8
    assert result["gender"] == "男"
    assert result["personality"] == "活泼"
    assert result["social"] == "喜欢交朋友"

@pytest.mark.asyncio
async def test_text_to_speech_tool(speech_processor_mock):
    """测试文本转语音工具"""
    tool = TextToSpeechTool(speech_processor_mock)
    args = SpeechInput(text="你好")
    
    with pytest.raises(NotImplementedError):
        tool._run(args)
    
    result = await tool._arun(args)
    assert result == b"audio_data"
    speech_processor_mock.text_to_speech.assert_called_once_with("你好")

@pytest.mark.asyncio
async def test_speech_to_text_tool(speech_processor_mock):
    """测试语音转文本工具"""
    tool = SpeechToTextTool(speech_processor_mock)
    args = AudioInput(audio_data=b"audio_data")
    
    with pytest.raises(NotImplementedError):
        tool._run(args)
    
    result = await tool._arun(args)
    assert result == "语音转文本结果"
    speech_processor_mock.speech_to_text.assert_called_once_with(b"audio_data")

@pytest.mark.asyncio
async def test_companion_agent(agent_mock):
    """测试AI伴侣代理"""
    # 测试文本处理
    response = await agent_mock.process_text("你好")
    assert isinstance(response, str)
    assert response == "你好！我是小美。"
    
    # 验证状态更新
    agent_mock.state_manager.update_last_interaction.assert_called_once()
    agent_mock.state_manager.add_to_history.assert_called()
    
    # 验证记忆保存
    agent_mock.memory.add_memory.assert_called_once()
    
    # 验证调用参数
    call_args = agent_mock.memory.add_memory.call_args
    assert call_args is not None
    args, kwargs = call_args
    
    # 由于 Mock 对象的调用方式可能不同，我们只验证关键内容
    assert "conversation" in str(call_args)  # memory_type
    assert "你好" in str(call_args)  # content
    assert "你好！我是小美。" in str(call_args)  # response in metadata

@pytest.mark.asyncio
async def test_agent_error_handling(agent_mock):
    """测试代理错误处理"""
    # 模拟错误情况
    agent_mock.memory.add_memory.side_effect = Exception("测试错误")
    agent_mock.agent_executor.ainvoke = AsyncMock(side_effect=Exception("代理执行错误"))
    
    response = await agent_mock.process_text("你好")
    assert "对不起" in response  # 确保返回了友好的错误消息

@pytest.mark.asyncio
async def test_input_validation():
    """测试输入验证"""
    # 测试记忆数量限制
    with pytest.raises(ValueError):
        MemoryInput(limit=0)
    with pytest.raises(ValueError):
        MemoryInput(limit=101)
    
    # 测试空内容
    with pytest.raises(ValueError):
        AddMemoryInput(content="")
    
    # 测试空状态
    with pytest.raises(ValueError):
        StateInput(state="")
    
    # 测试空话题
    with pytest.raises(ValueError):
        TopicInput(topic="") 