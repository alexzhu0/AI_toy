import sqlite3
from datetime import datetime
from typing import List, Dict
import json
from pathlib import Path
from config.settings import DATABASE
import logging

# 配置日志
logger = logging.getLogger(__name__)

class MemoryDB:
    def __init__(self):
        self.db_path = DATABASE['path']
        # 确保目录存在
        self.db_path.parent.mkdir(exist_ok=True)
        self.create_tables()
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def create_tables(self):
        """创建必要的数据库表"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 创建对话记录表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
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
                
                # 创建知识库表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT,
                    content TEXT,
                    source TEXT,
                    confidence FLOAT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    frequency INTEGER DEFAULT 1
                )
                ''')
                
                # 创建用户兴趣表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_interests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interest TEXT,
                    level INTEGER,
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
                    trigger TEXT,
                    context TEXT,
                    resolution TEXT
                )
                ''')
                
                # 添加索引以提高性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_topics ON conversations(topics)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_kb_topic ON knowledge_base(topic)')
                
                conn.commit()
        except Exception as e:
            logger.error(f"创建数据库表出错: {e}", exc_info=True)
            raise
    
    def add_conversation(self, user_input: str, ai_response: str, 
                        emotion: str = None, topics: List[str] = None,
                        context: str = None, session_id: str = None):
        """添加对话记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO conversations 
                (user_input, ai_response, emotion, topics, context, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_input, ai_response, emotion, 
                     json.dumps(topics or []), context, session_id))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"添加对话记录失败: {e}", exc_info=True)
            return None
    
    def get_recent_conversations(self, limit: int = 5, session_id: str = None) -> List[Dict]:
        """获取最近的对话记录"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                SELECT timestamp, user_input, ai_response, emotion, topics, context, session_id
                FROM conversations
                '''
                
                params = []
                if session_id:
                    query += ' WHERE session_id = ?'
                    params.append(session_id)
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                conversations = []
                for row in cursor.fetchall():
                    conversations.append({
                        'timestamp': row[0],
                        'user_input': row[1],
                        'ai_response': row[2],
                        'emotion': row[3],
                        'topics': json.loads(row[4]) if row[4] else [],
                        'context': row[5],
                        'session_id': row[6]
                    })
                return conversations
        except Exception as e:
            logger.error(f"获取对话记录失败: {e}", exc_info=True)
            return []
    
    def search_memories(self, keyword: str) -> List[Dict]:
        """搜索记忆"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT timestamp, user_input, ai_response, context
                FROM conversations
                WHERE user_input LIKE ? OR ai_response LIKE ?
                ORDER BY timestamp DESC
                ''', (f'%{keyword}%', f'%{keyword}%'))
                
                return [{'timestamp': row[0], 'user_input': row[1], 
                         'ai_response': row[2], 'context': row[3]}
                        for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}", exc_info=True)
            return []
    
    def add_knowledge(self, topic: str, content: str, source: str, confidence: float = 0.8):
        """添加知识条目"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在该知识
                cursor.execute('''
                SELECT id, frequency FROM knowledge_base
                WHERE topic = ? AND content = ?
                ''', (topic, content))
                
                existing = cursor.fetchone()
                if existing:
                    # 更新频率和置信度
                    cursor.execute('''
                    UPDATE knowledge_base
                    SET frequency = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (existing[1] + 1, existing[0]))
                else:
                    # 添加新知识
                    cursor.execute('''
                    INSERT INTO knowledge_base (topic, content, source, confidence)
                    VALUES (?, ?, ?, ?)
                    ''', (topic, content, source, confidence))
                
                conn.commit()
                return cursor.lastrowid if not existing else existing[0]
        except Exception as e:
            logger.error(f"添加知识失败: {e}", exc_info=True)
            return None
    
    def get_knowledge(self, topic: str = None, limit: int = 10) -> List[Dict]:
        """获取知识"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT topic, content, source, confidence, frequency FROM knowledge_base'
                params = []
                
                if topic:
                    query += ' WHERE topic LIKE ?'
                    params.append(f'%{topic}%')
                
                query += ' ORDER BY frequency DESC, confidence DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                return [{'topic': row[0], 'content': row[1], 'source': row[2], 
                         'confidence': row[3], 'frequency': row[4]}
                        for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取知识失败: {e}", exc_info=True)
            return []
    
    def close(self):
        """关闭连接（已废弃，使用上下文管理器代替）"""
        pass

def init_database():
    """初始化数据库"""
    try:
        db = MemoryDB()
        logger.info("数据库初始化成功")
        return db
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise 