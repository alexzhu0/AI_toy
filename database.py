import sqlite3
from datetime import datetime
from typing import List, Dict
import json
from pathlib import Path
from config.settings import DATABASE

class MemoryDB:
    def __init__(self):
        self.conn = sqlite3.connect('memories.db')
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        # 创建对话记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT,
            ai_response TEXT,
            emotion TEXT,
            topics TEXT
        )
        ''')
        
        # 创建记忆标签表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            tag TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
        ''')
        
        # 创建用户信息表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            personality TEXT,
            social TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        self.conn.commit()
    
    def add_conversation(self, user_input: str, ai_response: str, 
                        emotion: str = None, topics: List[str] = None):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO conversations (user_input, ai_response, emotion, topics)
        VALUES (?, ?, ?, ?)
        ''', (user_input, ai_response, emotion, json.dumps(topics or [])))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_recent_conversations(self, limit: int = 5) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT timestamp, user_input, ai_response, emotion, topics
        FROM conversations
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (limit,))
        
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'timestamp': row[0],
                'user_input': row[1],
                'ai_response': row[2],
                'emotion': row[3],
                'topics': json.loads(row[4])
            })
        return conversations
    
    def search_memories(self, keyword: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT timestamp, user_input, ai_response
        FROM conversations
        WHERE user_input LIKE ? OR ai_response LIKE ?
        ORDER BY timestamp DESC
        ''', (f'%{keyword}%', f'%{keyword}%'))
        
        return [{'timestamp': row[0], 'user_input': row[1], 'ai_response': row[2]}
                for row in cursor.fetchall()]
    
    def close(self):
        self.conn.close()

def init_database():
    """初始化数据库"""
    db_path = DATABASE['path']
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查并创建必要的表
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='conversations'
    """)
    table_exists = cursor.fetchone() is not None
    
    if table_exists:
        # 检查是否需要添加新列
        cursor.execute('PRAGMA table_info(conversations)')
        columns = [row[1] for row in cursor.fetchall()]
        
        # 添加缺失的列
        if 'context' not in columns:
            cursor.execute('ALTER TABLE conversations ADD COLUMN context TEXT')
        if 'session_id' not in columns:
            cursor.execute('ALTER TABLE conversations ADD COLUMN session_id TEXT')
    else:
        # 创建新表
        cursor.execute('''
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_input TEXT,
            ai_response TEXT,
            emotion TEXT,
            topics TEXT,
            context TEXT,
            session_id TEXT
        )
        ''')
    
    # 创建用户知识库表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,  -- 主题
        content TEXT,  -- 内容
        source TEXT,  -- 来源（对话/系统预设）
        confidence FLOAT,  -- 置信度
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        frequency INTEGER DEFAULT 1  -- 提及频率
    )
    ''')
    
    # 创建用户兴趣表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interest TEXT,
        level INTEGER,  -- 兴趣程度 1-5
        first_mentioned DATETIME,
        last_mentioned DATETIME,
        mention_count INTEGER DEFAULT 1
    )
    ''')
    
    # 创建情感记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emotion_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        emotion TEXT,
        trigger TEXT,  -- 触发因素
        context TEXT,  -- 情境描述
        resolution TEXT  -- 如何解决的
    )
    ''')
    
    # 提交事务
    conn.commit()
    
    return conn 