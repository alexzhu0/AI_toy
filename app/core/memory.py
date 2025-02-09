"""记忆管理模块"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from config.settings import DATABASE

class Memory:
    def __init__(self):
        self.db_path = DATABASE['path']
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
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
        
        conn.commit()
        conn.close()
    
    def add_memory(self, memory_type: str, content: str, metadata: Dict[str, Any] = None):
        """添加新的记忆"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        metadata_str = str(metadata) if metadata else None
        
        cursor.execute(
            'INSERT INTO memories (timestamp, type, content, metadata) VALUES (?, ?, ?, ?)',
            (timestamp, memory_type, content, metadata_str)
        )
        
        conn.commit()
        conn.close()
    
    def get_recent_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        conn = sqlite3.connect(self.db_path)
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
                'metadata': eval(row[4]) if row[4] else None
            })
        
        conn.close()
        return memories 