#!/usr/bin/env python3
"""
配置检查工具
用于检查环境配置、依赖和必要的文件是否存在
"""

import os
import sys
import logging
import importlib.util
from pathlib import Path
import dotenv
import sqlite3
import asyncio
import subprocess

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ConfigCheck")

def check_python_version():
    """检查Python版本"""
    logger.info("检查Python版本...")
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        logger.error(f"Python版本过低: {python_version.major}.{python_version.minor}，需要Python 3.8或更高版本")
        return False
    logger.info(f"Python版本 {python_version.major}.{python_version.minor}.{python_version.micro} ✓")
    return True

def check_dependencies():
    """检查关键依赖项"""
    logger.info("检查依赖项...")
    required_packages = [
        "fastapi", "uvicorn", "openai", "edge_tts", "numpy", 
        "soundfile", "pydantic", "langchain"
    ]
    missing_packages = []
    
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"缺少以下依赖: {', '.join(missing_packages)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False
    
    logger.info("所有依赖已安装 ✓")
    return True

def check_directories():
    """检查必要的目录结构"""
    logger.info("检查目录结构...")
    base_dir = Path(__file__).parent
    required_dirs = [
        base_dir / "data",
        base_dir / "app",
        base_dir / "config",
        base_dir / "ssl"
    ]
    
    missing_dirs = []
    for directory in required_dirs:
        if not directory.exists():
            missing_dirs.append(directory)
    
    if missing_dirs:
        logger.error(f"缺少以下目录: {', '.join(str(d) for d in missing_dirs)}")
        return False
    
    logger.info("目录结构检查通过 ✓")
    return True

def check_environment_variables():
    """检查环境变量配置"""
    logger.info("检查环境变量...")
    
    # 尝试加载.env文件
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        logger.info(f"加载环境变量文件: {env_file}")
        dotenv.load_dotenv(env_file)
    
    required_vars = ["DEEPSEEK_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"缺少以下环境变量: {', '.join(missing_vars)}")
        logger.info("请创建.env文件并设置必要的环境变量")
        return False
    
    logger.info("环境变量检查通过 ✓")
    return True

def check_database():
    """检查数据库配置"""
    logger.info("检查数据库...")
    from config.settings import DATABASE
    
    db_path = DATABASE.get('path')
    if not db_path:
        logger.error("配置中没有数据库路径")
        return False
    
    # 确保目录存在
    db_path.parent.mkdir(exist_ok=True)
    
    # 测试数据库连接
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.info("数据库连接成功 ✓")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return False

async def check_network():
    """检查网络连接"""
    logger.info("检查网络连接...")
    
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            # 测试DeepSeek API连接
            async with session.get('https://api.deepseek.com/healthz', timeout=5) as resp:
                if resp.status == 200:
                    logger.info("DeepSeek API连接成功 ✓")
                    return True
                else:
                    logger.error(f"DeepSeek API连接失败，状态码: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"网络测试失败: {e}")
        return False

def run_system_check():
    """运行系统检查"""
    try:
        # 检查麦克风和扬声器
        import sounddevice as sd
        devices = sd.query_devices()
        
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        
        if not input_devices:
            logger.error("未检测到麦克风设备")
            return False
        
        if not output_devices:
            logger.error("未检测到扬声器设备")
            return False
        
        logger.info(f"检测到 {len(input_devices)} 个输入设备和 {len(output_devices)} 个输出设备 ✓")
        
        # 显示当前默认设备
        logger.info(f"默认输入设备: {sd.query_devices(kind='input')['name']}")
        logger.info(f"默认输出设备: {sd.query_devices(kind='output')['name']}")
        
        return True
    except Exception as e:
        logger.error(f"音频设备检查失败: {e}")
        return False

def check_ssl_certificates():
    """检查SSL证书"""
    logger.info("检查SSL证书...")
    ssl_dir = Path(__file__).parent / "ssl"
    
    key_file = ssl_dir / "key.pem"
    cert_file = ssl_dir / "cert.pem"
    
    if not key_file.exists() or not cert_file.exists():
        logger.warning(f"缺少SSL证书文件，密钥: {'✓' if key_file.exists() else '✗'}, 证书: {'✓' if cert_file.exists() else '✗'}")
        return False
    
    logger.info("SSL证书检查通过 ✓")
    return True

async def main():
    """主函数"""
    print("=" * 50)
    print("       AI Toy 配置检查工具")
    print("=" * 50)
    
    # 系统级检查
    all_passed = check_python_version()
    
    # 环境检查
    all_passed = check_dependencies() and all_passed
    all_passed = check_directories() and all_passed
    all_passed = check_environment_variables() and all_passed
    all_passed = check_ssl_certificates() and all_passed
    
    # 数据库检查
    try:
        all_passed = check_database() and all_passed
    except Exception as e:
        logger.error(f"数据库检查失败: {e}")
        all_passed = False
    
    # 系统设备检查
    all_passed = run_system_check() and all_passed
    
    # 网络检查
    try:
        network_check = await check_network()
        all_passed = network_check and all_passed
    except Exception as e:
        logger.error(f"网络检查失败: {e}")
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ 所有检查通过！系统准备就绪。")
    else:
        print("❌ 部分检查未通过。请修复上述问题后再运行程序。")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main()) 