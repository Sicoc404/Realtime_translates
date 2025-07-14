#!/usr/bin/env python3
"""
LiveKit Agent - 符合官方文档的实时翻译实现
使用STT-LLM-TTS管道架构
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions
from livekit.plugins import groq, deepgram, cartesia

from translation_prompts import KR_PROMPT, VN_PROMPT

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 环境变量
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY", "")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# 检查必要的API密钥
if not GROQ_API_KEY:
    logger.error("❌ GROQ_API_KEY 未设置")
if not DEEPGRAM_API_KEY:
    logger.error("❌ DEEPGRAM_API_KEY 未设置")
if not CARTESIA_API_KEY:
    logger.error("❌ CARTESIA_API_KEY 未设置")
if not LIVEKIT_URL:
    logger.error("❌ LIVEKIT_URL 未设置")
if not LIVEKIT_API_KEY:
    logger.error("❌ LIVEKIT_API_KEY 未设置")
if not LIVEKIT_API_SECRET:
    logger.error("❌ LIVEKIT_API_SECRET 未设置")


class TranslationAgent(Agent):
    """实时翻译Agent"""
    
    def __init__(self, lang_code: str, prompt: str):
        super().__init__(instructions=prompt)
        self.lang_code = lang_code
        self.prompt = prompt
        logger.info(f"🤖 创建翻译Agent: {lang_code}")


async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent 入口点函数
    按照官方文档实现STT-LLM-TTS管道
    """
    
    # 连接到房间
    await ctx.connect()
    
    # 获取房间名称来确定翻译类型和提示词
    room_name = ctx.room.name
    logger.info(f"🏠 Agent加入房间: {room_name}")
    
    # 根据房间名称确定翻译类型和提示词
    if room_name == "zh":
        # 中文原音房间 - 直接转发原始音频
        agent_prompt = "你是一个中文语音助手，直接重复用户说的中文内容。"
        agent = TranslationAgent("zh", agent_prompt)
        logger.info("🇨🇳 设置中文原音Agent")
    elif room_name == "kr":
        # 韩文翻译房间
        agent = TranslationAgent("kr", KR_PROMPT)
        logger.info("🇰🇷 设置韩文翻译Agent")
    elif room_name == "vn":
        # 越南文翻译房间
        agent = TranslationAgent("vn", VN_PROMPT)
        logger.info("🇻🇳 设置越南文翻译Agent")
    else:
        # 默认中文房间
        agent_prompt = "你是一个中文语音助手，直接重复用户说的中文内容。"
        agent = TranslationAgent("zh", agent_prompt)
        logger.info("🔄 设置默认中文Agent")
    
    # 创建AgentSession - 按照官方文档的STT-LLM-TTS管道
    try:
        session = AgentSession(
            stt=deepgram.STT(
                model="nova-2",
                language="zh"  # 中文语音识别
            ),
            llm=groq.LLM(
                model="llama3-8b-8192"
            ),
            tts=cartesia.TTS(
                model="sonic-multilingual",
                voice="a0e99841-438c-4a64-b679-ae501e7d6091"  # 多语言语音合成
            ),
        )
        
        logger.info(f"🔧 创建AgentSession用于房间: {room_name}")
        
        # 启动会话
        await session.start(
            room=ctx.room,
            agent=agent
        )
        
        logger.info(f"▶️ AgentSession已启动用于房间: {room_name}")
        logger.info(f"🎧 Agent正在监听房间 {room_name} 中的音频流...")
        
        # 生成初始回复（可选）
        try:
            if room_name == "kr":
                await session.generate_reply(
                    instructions="房间已准备好进行中文到韩文的实时翻译。"
                )
            elif room_name == "vn":
                await session.generate_reply(
                    instructions="房间已准备好进行中文到越南文的实时翻译。"
                )
            else:
                await session.generate_reply(
                    instructions="中文原音房间已准备就绪。"
                )
            logger.info(f"🔊 已发送初始欢迎消息到房间: {room_name}")
        except Exception as e:
            logger.warning(f"发送初始消息失败: {str(e)}")
            
    except Exception as e:
        logger.error(f"❌ 创建AgentSession失败: {str(e)}")
        raise


# 主函数 - 用于测试
if __name__ == "__main__":
    # 创建工作器选项，确保使用正确的环境变量
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        # 使用环境变量中的LIVEKIT_URL
        livekit_url=LIVEKIT_URL,
        # 设置Agent名称以启用显式调度
        agent_name="translation-agent",
        # 开发模式设置
        load_threshold=float('inf'),  # 开发模式下不限制负载
    )
    agents.cli.run_app(worker_options) 
