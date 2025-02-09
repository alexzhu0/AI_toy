import os
from pathlib import Path
from app.web.server import WebServer
from config.settings import BASE_DIR, DATA_DIR, MODELS_DIR, MODEL_CONFIG
import asyncio
from dotenv import load_dotenv

def init_directories():
    """初始化必要的目录结构"""
    # 创建数据目录
    DATA_DIR.mkdir(exist_ok=True)
    
    # 创建 SSL 目录
    ssl_dir = BASE_DIR / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    
    # 移动证书文件到 ssl 目录
    key_file = BASE_DIR / "key.pem"
    cert_file = BASE_DIR / "cert.pem"
    if key_file.exists():
        key_file.rename(ssl_dir / "key.pem")
    if cert_file.exists():
        cert_file.rename(ssl_dir / "cert.pem")

def main():
    # 加载环境变量
    load_dotenv()
    
    # 初始化必要的目录
    DATA_DIR.mkdir(exist_ok=True)
    
    # 初始化目录结构
    init_directories()
    
    # 设置环境变量
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_DATASETS_OFFLINE'] = '1'
    
    # 运行服务器
    server = WebServer()
    asyncio.run(server.start())

if __name__ == "__main__":
    main() 