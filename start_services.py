#!/usr/bin/env python3
"""
启动脚本 - 同时启动Web服务和Agent服务
"""

import os
import sys
import asyncio
import subprocess
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """检查必要的环境变量"""
    required_vars = [
        'GROQ_API_KEY',
        'LIVEKIT_API_KEY', 
        'LIVEKIT_API_SECRET',
        'LIVEKIT_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ 所有必要的环境变量已配置")
    return True

async def start_web_service():
    """启动Web服务"""
    logger.info("🌐 启动Web服务...")
    
    port = int(os.environ.get("PORT", 8000))
    
    # 启动FastAPI服务
    process = await asyncio.create_subprocess_exec(
        sys.executable, "main.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    logger.info(f"🌐 Web服务已启动在端口 {port}")
    return process

async def start_agent_service():
    """启动Agent服务"""
    logger.info("🤖 启动Agent服务...")
    
    # 启动Agent服务
    process = await asyncio.create_subprocess_exec(
        sys.executable, "agent_runner.py", "dev",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    logger.info("🤖 Agent服务已启动")
    return process

async def main():
    """主函数"""
    logger.info("🚀 启动实时翻译服务...")
    
    # 检查环境变量
    if not check_environment():
        sys.exit(1)
    
    try:
        # 启动Web服务
        web_process = await start_web_service()
        
        # 等待一会儿让Web服务启动
        await asyncio.sleep(2)
        
        # 启动Agent服务
        agent_process = await start_agent_service()
        
        logger.info("✅ 所有服务已启动")
        logger.info("📡 Web服务: http://localhost:8000")
        logger.info("🤖 Agent服务: 已连接到LiveKit")
        logger.info("🎯 支持的房间: room_zh, room_kr, room_vn")
        logger.info("⚠️  按 Ctrl+C 停止所有服务")
        
        # 等待进程完成
        await asyncio.gather(
            web_process.wait(),
            agent_process.wait()
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 接收到停止信号，正在关闭服务...")
        
        # 终止进程
        if 'web_process' in locals():
            web_process.terminate()
        if 'agent_process' in locals():
            agent_process.terminate()
        
        logger.info("✅ 所有服务已关闭")
    
    except Exception as e:
        logger.error(f"❌ 启动服务失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 