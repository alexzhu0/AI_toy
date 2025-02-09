"""状态管理模块"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime
import json

@dataclass
class UserState:
    """用户状态"""
    name: str
    age: int
    gender: str
    personality: str
    social: str

@dataclass
class ConversationState:
    """对话状态"""
    last_interaction: Optional[datetime] = None
    conversation_history: list = None
    current_topic: Optional[str] = None
    emotional_state: Optional[str] = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.last_interaction is None:
            self.last_interaction = datetime.now()

class StateManager:
    def __init__(self, user_config: Dict[str, Any]):
        self.user_state = UserState(**user_config['profile'])
        self.conversation_state = ConversationState()
    
    def update_last_interaction(self):
        """更新最后交互时间"""
        self.conversation_state.last_interaction = datetime.now()
    
    def add_to_history(self, role: str, content: str):
        """添加对话历史"""
        self.conversation_state.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_recent_history(self, limit: int = 10) -> list:
        """获取最近的对话历史"""
        return self.conversation_state.conversation_history[-limit:]
    
    def set_emotional_state(self, state: str):
        """设置情感状态"""
        self.conversation_state.emotional_state = state
    
    def set_current_topic(self, topic: str):
        """设置当前话题"""
        self.conversation_state.current_topic = topic
    
    def to_dict(self) -> Dict[str, Any]:
        """将状态转换为字典"""
        return {
            'user': asdict(self.user_state),
            'conversation': {
                'last_interaction': self.conversation_state.last_interaction.isoformat(),
                'conversation_history': self.conversation_state.conversation_history,
                'current_topic': self.conversation_state.current_topic,
                'emotional_state': self.conversation_state.emotional_state
            }
        }
    
    def save_state(self, file_path: str):
        """保存状态到文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_state(cls, file_path: str, user_config: Dict[str, Any]):
        """从文件加载状态"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            instance = cls(user_config)
            instance.user_state = UserState(**data['user'])
            
            conv_data = data['conversation']
            instance.conversation_state.last_interaction = datetime.fromisoformat(
                conv_data['last_interaction']
            )
            instance.conversation_state.conversation_history = conv_data['conversation_history']
            instance.conversation_state.current_topic = conv_data['current_topic']
            instance.conversation_state.emotional_state = conv_data['emotional_state']
            
            return instance
        except FileNotFoundError:
            return cls(user_config) 