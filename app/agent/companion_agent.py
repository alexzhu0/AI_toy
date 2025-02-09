"""AI伴侣代理模块"""
import os
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel, Field

from app.core.memory import Memory
from app.core.state import StateManager
from app.core.speech import SpeechProcessor
from app.agent.prompts import SYSTEM_PROMPT, INTERACTION_PROMPT
from app.agent.tools import get_all_tools

class AgentState(BaseModel):
    """代理状态"""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    current_topic: Optional[str] = None
    emotional_state: Optional[str] = None

class CompanionAgent:
    def __init__(
        self,
        memory: Memory,
        state_manager: StateManager,
        speech_processor: SpeechProcessor
    ):
        self.memory = memory
        self.state_manager = state_manager
        self.speech_processor = speech_processor
        
        # 初始化 LangChain 组件
        self.llm = ChatOpenAI(
            openai_api_key=os.getenv('DEEPSEEK_API_KEY'),
            openai_api_base=os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1'),
            model_name="deepseek-chat",
            temperature=0.7,
            max_tokens=2000,
            model_kwargs={"response_format": {"type": "text"}},
            streaming=True
        )
        
        # 获取所有工具
        self.tools = get_all_tools(memory, state_manager, speech_processor)
        
        # 创建对话记忆
        self.conversation_memory = ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history",
            output_key="output",
            input_key="input"
        )
        
        # 创建代理
        system_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT)
        tools_prompt = SystemMessagePromptTemplate.from_template("可用工具:\n{tools}")
        human_prompt = HumanMessagePromptTemplate.from_template("{input}")
        
        prompt = ChatPromptTemplate.from_messages([
            system_prompt,
            tools_prompt,
            MessagesPlaceholder(variable_name="chat_history"),
            human_prompt,
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        tool_strings = "\n".join(f"- {tool.name}: {tool.description}" for tool in self.tools)
        
        self.agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt.partial(tools=tool_strings)
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.conversation_memory,
            verbose=True,
            max_iterations=3,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )
    
    def _build_prompt(self, user_input: str) -> str:
        """构建提示词"""
        user_state = self.state_manager.user_state
        state_prompt = INTERACTION_PROMPT.format(
            name=user_state.name,
            age=user_state.age,
            gender=user_state.gender,
            personality=user_state.personality,
            social=user_state.social
        )
        
        return f"{state_prompt}\n\n{user_input}"
    
    async def process_text(self, text: str) -> str:
        """处理文本输入并生成响应"""
        try:
            print(f"收到用户输入: {text}")  # 调试日志
            
            # 构建提示词
            prompt = self._build_prompt(text)
            print(f"构建后的提示词: {prompt}")  # 调试日志
            
            try:
                response = await self.agent_executor.ainvoke({
                    "input": prompt,
                    "chat_history": self.conversation_memory.chat_memory.messages
                })
                print(f"代理响应: {response}")  # 调试日志
            except Exception as e:
                print(f"代理执行错误: {e}")
                return "对不起，我现在遇到了一些问题，能稍后再聊吗？"
            
            # 检查响应结构
            if not isinstance(response, dict):
                print(f"意外的响应类型: {type(response)}")
                return "对不起，我没有理解你的意思，能换个方式说吗？"
            
            result = response.get("output")
            if result is None:
                print(f"响应中没有output字段: {response}")
                return "对不起，我没有理解你的意思，能换个方式说吗？"
            
            try:
                # 更新状态
                self.state_manager.update_last_interaction()
                self.state_manager.add_to_history("user", text)
                self.state_manager.add_to_history("assistant", result)
            except Exception as e:
                print(f"更新状态时出错: {e}")
                # 继续执行，不影响对话
            
            try:
                # 保存到记忆
                self.memory.add_memory(
                    memory_type="conversation",
                    content=text,
                    metadata={
                        "response": result,
                        "timestamp": datetime.now().isoformat(),
                        "intermediate_steps": response.get("intermediate_steps", [])
                    }
                )
            except Exception as e:
                print(f"保存记忆时出错: {e}")
                # 继续执行，不影响对话
            
            return result
            
        except Exception as e:
            print(f"处理文本时出错: {e}")
            return "对不起，我现在有点累了，能稍后再聊吗？" 