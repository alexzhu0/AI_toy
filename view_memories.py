import sqlite3
from pathlib import Path

def view_memories():
    # 连接数据库
    db_path = Path(__file__).parent / "data" / "memories.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查看对话历史
    print("\n=== 最近的对话 ===")
    cursor.execute('''
        SELECT timestamp, user_input, ai_response 
        FROM conversations 
        ORDER BY timestamp DESC 
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f"\n时间: {row[0]}")
        print(f"用户: {row[1]}")
        print(f"小美: {row[2]}")
    
    # 查看知识库
    print("\n=== 知识库内容 ===")
    cursor.execute('SELECT topic, content, frequency FROM knowledge_base')
    for row in cursor.fetchall():
        print(f"\n主题: {row[0]}")
        print(f"内容: {row[1]}")
        print(f"提及次数: {row[2]}")
    
    # 查看情感记录
    print("\n=== 情感记录 ===")
    cursor.execute('SELECT timestamp, emotion, trigger FROM emotion_records')
    for row in cursor.fetchall():
        print(f"\n时间: {row[0]}")
        print(f"情绪: {row[1]}")
        print(f"触发: {row[2]}")
    
    conn.close()

if __name__ == "__main__":
    view_memories() 