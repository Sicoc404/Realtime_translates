#!/usr/bin/env python3
"""
DNS和连接测试脚本
"""

import os
import socket
import ssl
import asyncio
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_dns_resolution():
    """测试DNS解析"""
    logger.info("🔍 开始DNS解析测试...")
    
    # 测试基本DNS解析
    test_domains = [
        "google.com",
        "github.com", 
        "api.groq.com",
        "api.deepgram.com",
        "api.cartesia.ai"
    ]
    
    for domain in test_domains:
        try:
            ip = socket.gethostbyname(domain)
            logger.info(f"✅ {domain} -> {ip}")
        except Exception as e:
            logger.error(f"❌ {domain} 解析失败: {str(e)}")
    
    # 测试LiveKit URL
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    if livekit_url and "://" in livekit_url:
        livekit_host = livekit_url.replace("wss://", "").replace("https://", "").split("/")[0].split(":")[0]
        logger.info(f"🔍 测试LiveKit主机: {livekit_host}")
        try:
            ip = socket.gethostbyname(livekit_host)
            logger.info(f"✅ LiveKit主机 {livekit_host} -> {ip}")
        except Exception as e:
            logger.error(f"❌ LiveKit主机解析失败: {str(e)}")
    else:
        logger.error("❌ LIVEKIT_URL未设置或格式错误")


def test_ssl_connection():
    """测试SSL连接"""
    logger.info("🔒 开始SSL连接测试...")
    
    test_hosts = [
        ("api.groq.com", 443),
        ("api.deepgram.com", 443),
        ("api.cartesia.ai", 443)
    ]
    
    for host, port in test_hosts:
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            
            # 测试连接
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    logger.info(f"✅ SSL连接成功: {host}:{port}")
                    
        except Exception as e:
            logger.error(f"❌ SSL连接失败 {host}:{port}: {str(e)}")


def test_livekit_websocket():
    """测试LiveKit WebSocket连接"""
    logger.info("🌐 开始LiveKit WebSocket连接测试...")
    
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    if not livekit_url:
        logger.error("❌ LIVEKIT_URL未设置")
        return
    
    try:
        import websockets
        
        async def test_ws():
            try:
                # 简单的WebSocket连接测试（不带认证）
                test_url = livekit_url.replace("/rtc", "") if "/rtc" in livekit_url else livekit_url
                logger.info(f"🔍 测试WebSocket连接: {test_url}")
                
                # 注意：这只是测试连接，不进行认证
                async with websockets.connect(test_url, timeout=10) as websocket:
                    logger.info("✅ WebSocket连接成功（基础连接测试）")
                    
            except Exception as e:
                logger.warning(f"⚠️ WebSocket连接测试: {str(e)}")
                logger.info("💡 这可能是正常的，因为我们没有提供认证信息")
        
        asyncio.run(test_ws())
        
    except ImportError:
        logger.warning("⚠️ websockets库未安装，跳过WebSocket测试")
    except Exception as e:
        logger.error(f"❌ WebSocket测试失败: {str(e)}")


def test_environment_variables():
    """测试环境变量"""
    logger.info("🔍 开始环境变量测试...")
    
    required_vars = [
        "GROQ_API_KEY",
        "DEEPGRAM_API_KEY", 
        "CARTESIA_API_KEY",
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.environ.get(var, "")
        if value:
            # 只显示前8个字符，保护敏感信息
            masked_value = value[:8] + "..." if len(value) > 8 else value
            logger.info(f"✅ {var}: {masked_value}")
        else:
            missing_vars.append(var)
            logger.error(f"❌ {var}: 未设置")
    
    if missing_vars:
        logger.error(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        return False
    else:
        logger.info("✅ 所有必要的环境变量已设置")
        return True


def main():
    """主函数"""
    logger.info("🚀 开始系统连接测试...")
    
    # 1. 测试环境变量
    env_ok = test_environment_variables()
    
    # 2. 测试DNS解析
    test_dns_resolution()
    
    # 3. 测试SSL连接
    test_ssl_connection()
    
    # 4. 测试LiveKit WebSocket
    test_livekit_websocket()
    
    logger.info("🏁 系统连接测试完成")
    
    if env_ok:
        logger.info("✅ 系统配置正常，可以尝试启动LiveKit Agent")
    else:
        logger.error("❌ 系统配置有问题，请检查环境变量")


if __name__ == "__main__":
    main() 