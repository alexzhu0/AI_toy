"""记忆管理模块"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from config.settings import DATABASE
import json
import logging

logger = logging.getLogger(__name__)

class Memory:
    def __init__(self):
        self.db_path = DATABASE['path']
        self._init_db()
        # 确保数据目录存在
        self.db_path.parent.mkdir(exist_ok=True)
    
    def _init_db(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建记忆表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # 添加索引以提高查询性能
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp 
                ON memories(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memories_type 
                ON memories(type)
            ''')
            
            conn.commit()
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def add_memory(self, memory_type: str, content: str, metadata: Dict[str, Any] = None):
        """添加新的记忆"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                timestamp = datetime.now().isoformat()
                metadata_str = json.dumps(metadata) if metadata else None
                
                cursor.execute(
                    'INSERT INTO memories (timestamp, type, content, metadata) VALUES (?, ?, ?, ?)',
                    (timestamp, memory_type, content, metadata_str)
                )
                
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"添加记忆失败: {e}", exc_info=True)
            return None
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    'SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?',
                    (limit,)
                )
                
                memories = []
                for row in cursor.fetchall():
                    memories.append({
                        'id': row[0],
                        'timestamp': row[1],
                        'type': row[2],
                        'content': row[3],
                        'metadata': json.loads(row[4]) if row[4] else None
                    })
                
                return memories
        except Exception as e:
            logger.error(f"获取记忆失败: {e}", exc_info=True)
            return []
    
    def search_memories(self, keyword: str, memory_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索记忆"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM memories WHERE content LIKE ?'
                params = [f'%{keyword}%']
                
                if memory_type:
                    query += ' AND type = ?'
                    params.append(memory_type)
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                memories = []
                for row in cursor.fetchall():
                    memories.append({
                        'id': row[0],
                        'timestamp': row[1],
                        'type': row[2],
                        'content': row[3],
                        'metadata': json.loads(row[4]) if row[4] else None
                    })
                
                return memories
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}", exc_info=True)
            return [] 