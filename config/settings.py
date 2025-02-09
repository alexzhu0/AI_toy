from pathlib import Path
import os

# 基础路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# 数据库配置
DATABASE = {
    'path': DATA_DIR / "memories.db",
    'backup_path': DATA_DIR / "backup"
}

# 服务器配置
SERVER_CONFIG = {
    'host': '0.0.0.0',
    'port': 8001,
    'ssl': {
        'enabled': True,
        'key_file': BASE_DIR / "ssl" / "key.pem",
        'cert_file': BASE_DIR / "ssl" / "cert.pem"
    }
}

# API配置
API_CONFIG = {
    'deepseek': {
        'api_key': os.getenv('DEEPSEEK_API_KEY', ''),
        'api_base': 'https://api.deepseek.com/v1',
        'model': 'deepseek-chat',
        'model_kwargs': {
            'temperature': 0.7,
            'max_tokens': 2000,
            'top_p': 0.9
        }
    }
}

# 用户配置
USER_CONFIG = {
    'profile': {
        'name': "帅帅",
        'age': 5,
        'gender': "男生",
        'personality': "腼腆害羞",
        'social': "没有什么朋友"
    },
    'interaction_style': {
        'tone': "温柔耐心",
        'goals': [
            "多鼓励他表达自己",
            "帮助他建立自信",
            "引导他学会交朋友"
        ],
        'rules': [
            "说话要简单易懂",
            "多用具体的例子",
            "给予积极的反馈",
            "保持耐心和包容"
        ]
    }
}

# 语音配置
SPEECH = {
    'voice': "zh-CN-XiaoxiaoNeural",  # Edge TTS 的声音
}

# 模型配置
MODEL_CONFIG = {
    'whisper': {
        'path': '/Users/alex/AI/AI_toy/models',
        'local_path': '/Users/alex/AI/AI_toy/models',
        'device': "cpu",
        'compute_type': "float32",
        'language': 'zh',
        'offline': True
    }
} 