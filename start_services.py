#!/usr/bin/env python3
"""
启动翻译服务脚本 - 用于启动LiveKit Agent和测试组件
"""

import os
import sys
import argparse
import asyncio
import logging
import subprocess
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("translation_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("translation_service")

# 加载环境变量
load_dotenv()

# 检查环境变量
def check_env_variables():
    """检查必要的环境变量是否设置"""
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
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ 缺少以下环境变量: {', '.join(missing_vars)}")
        return False
    
    logger.info("✅ 所有必要的环境变量已设置")
    return True


# 测试组件
async def test_components(component=None, text=None, audio_file=None, language=None):
    """测试各个组件"""
    from test_components import test_stt, test_llm, test_tts, test_full_pipeline, test_record_audio
    
    if component == "stt":
        audio_path = audio_file or "test_audio.wav"
        logger.info(f"🎤 测试STT组件，使用音频文件: {audio_path}")
        result = await test_stt(audio_path)
        return result
    
    elif component == "llm":
        input_text = text or "你好，今天天气真不错"
        target_lang = language or "kr"
        logger.info(f"🧠 测试LLM组件，输入文本: {input_text}, 目标语言: {target_lang}")
        result = await test_llm(input_text, target_lang)
        return result
    
    elif component == "tts":
        input_text = text or "안녕하세요, 오늘 날씨가 정말 좋네요"
        lang_code = language or "ko"
        logger.info(f"🔊 测试TTS组件，输入文本: {input_text}, 语言: {lang_code}")
        result = await test_tts(input_text, lang_code)
        return result
    
    elif component == "pipeline":
        audio_path = audio_file or "test_audio.wav"
        target_lang = language or "kr"
        logger.info(f"🔄 测试完整翻译管道: {audio_path} -> {target_lang}")
        result = await test_full_pipeline(audio_path, target_lang)
        return result
    
    elif component == "record":
        duration = 5
        output_file = audio_file or "test_audio.wav"
        logger.info(f"🎤 录制测试音频，时长: {duration}秒，保存到: {output_file}")
        result = await test_record_audio(duration, output_file)
        return result
    
    else:
        logger.error(f"❌ 未知组件: {component}")
        return None


# 启动LiveKit Agent
def start_livekit_agent():
    """启动LiveKit Agent服务"""
    logger.info("🚀 启动LiveKit Agent服务...")
    
    try:
        # 使用subprocess启动livekit_agent.py
        process = subprocess.Popen(
            [sys.executable, "livekit_agent.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"✅ LiveKit Agent服务已启动，进程ID: {process.pid}")
        return process
    except Exception as e:
        logger.error(f"❌ 启动LiveKit Agent服务失败: {str(e)}")
        return None


# 启动Web服务
def start_web_server(host="0.0.0.0", port=8000):
    """启动Web服务器"""
    logger.info(f"🚀 启动Web服务器，地址: {host}:{port}...")
    
    try:
        # 使用subprocess启动uvicorn服务器
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "web_only:app", "--host", host, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"✅ Web服务器已启动，进程ID: {process.pid}")
        logger.info(f"📊 Web界面可通过 http://{host}:{port} 访问")
        return process
    except Exception as e:
        logger.error(f"❌ 启动Web服务器失败: {str(e)}")
        return None


# 关闭进程
def stop_process(process, name):
    """停止进程"""
    if process:
        logger.info(f"🛑 停止{name}...")
        try:
            process.terminate()
            process.wait(timeout=5)
            logger.info(f"✅ {name}已停止")
        except Exception as e:
            logger.error(f"❌ 停止{name}失败: {str(e)}")
            try:
                process.kill()
                logger.info(f"✅ {name}已强制终止")
            except:
                logger.error(f"❌ 无法终止{name}")


# 主函数
async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动翻译服务和测试组件")
    
    # 添加命令行参数
    parser.add_argument("--test", choices=["stt", "llm", "tts", "pipeline", "record"], 
                        help="测试特定组件")
    parser.add_argument("--text", help="用于测试的文本")
    parser.add_argument("--audio", help="用于测试的音频文件路径")
    parser.add_argument("--lang", help="目标语言代码")
    parser.add_argument("--start-agent", action="store_true", help="启动LiveKit Agent服务")
    parser.add_argument("--start-web", action="store_true", help="启动Web服务器")
    parser.add_argument("--host", default="0.0.0.0", help="Web服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="Web服务器端口")
    
    args = parser.parse_args()
    
    # 检查环境变量
    if not check_env_variables():
        logger.error("❌ 环境变量检查失败，请检查.env文件")
        return
    
    # 启动服务
    agent_process = None
    web_process = None
    
    try:
        # 测试组件
        if args.test:
            result = await test_components(
                component=args.test,
                text=args.text,
                audio_file=args.audio,
                language=args.lang
            )
            if result is not None:
                logger.info(f"✅ 测试完成: {args.test}")
        
        # 启动LiveKit Agent
        if args.start_agent:
            agent_process = start_livekit_agent()
        
        # 启动Web服务器
        if args.start_web:
            web_process = start_web_server(args.host, args.port)
        
        # 如果启动了服务，保持脚本运行
        if agent_process or web_process:
            logger.info("🔄 服务已启动，按Ctrl+C停止...")
            while True:
                await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("👋 收到停止信号，正在关闭服务...")
    
    finally:
        # 关闭服务
        if agent_process:
            stop_process(agent_process, "LiveKit Agent服务")
        
        if web_process:
            stop_process(web_process, "Web服务")
        
        logger.info("🏁 所有服务已停止")


if __name__ == "__main__":
    asyncio.run(main()) 
