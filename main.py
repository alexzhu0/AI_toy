import os
import sys
from pathlib import Path
from app.web.server import WebServer
from config.settings import BASE_DIR, DATA_DIR, MODELS_DIR, MODEL_CONFIG
import asyncio
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "app.log"),
    ]
)
logger = logging.getLogger(__name__)

def init_directories():
    """初始化必要的目录结构"""
    try:
        # 创建数据目录
        DATA_DIR.mkdir(exist_ok=True)
        logger.info(f"数据目录已初始化: {DATA_DIR}")
        
        # 创建模型目录
        MODELS_DIR.mkdir(exist_ok=True)
        logger.info(f"模型目录已初始化: {MODELS_DIR}")
        
        # 创建 SSL 目录
        ssl_dir = BASE_DIR / "ssl"
        ssl_dir.mkdir(exist_ok=True)
        logger.info(f"SSL目录已初始化: {ssl_dir}")
        
        # 移动证书文件到 ssl 目录
        key_file = BASE_DIR / "key.pem"
        cert_file = BASE_DIR / "cert.pem"
        if key_file.exists():
            key_file.rename(ssl_dir / "key.pem")
            logger.info("密钥文件已移动到SSL目录")
        if cert_file.exists():
            cert_file.rename(ssl_dir / "cert.pem")
            logger.info("证书文件已移动到SSL目录")
            
    except Exception as e:
        logger.error(f"初始化目录时出错: {e}", exc_info=True)
        raise

async def main():
    try:
        # 加载环境变量
        load_dotenv()
        logger.info("环境变量已加载")
        
        # 初始化必要的目录
        init_directories()
        
        # 设置环境变量
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_DATASETS_OFFLINE'] = '1'
        logger.info("离线模式环境变量已设置")
        
        # 检查API密钥
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            logger.warning("未设置DEEPSEEK_API_KEY环境变量，某些功能可能不可用")
        
        # 运行服务器
        logger.info("正在启动Web服务器...")
        server = WebServer()
        await server.start()
        
    except KeyboardInterrupt:
        logger.info("接收到键盘中断，程序退出")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"启动过程中发生严重错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 