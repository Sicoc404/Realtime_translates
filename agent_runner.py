#!/usr/bin/env python3
"""
LiveKit Agent Runner - 使用Groq LLM进行实时翻译
严格按照LiveKit官方文档实现
"""

import asyncio
import os
import logging
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent
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

# 房间名称
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间  
ROOM_VN = "room_vn"  # 越南文翻译房间

class TranslationAgent(Agent):
    """实时翻译Agent"""
    
    def __init__(self, lang_code: str, prompt: str):
        super().__init__(instructions=prompt)
        self.lang_code = lang_code
        self.prompt = prompt
        logger.info(f"🤖 Created TranslationAgent for {lang_code}")

async def entrypoint(ctx: agents.JobContext):
    """
    LiveKit Agent 入口点函数
    按照官方文档实现STT-LLM-TTS管道
    """
    
    # 获取房间名称来确定翻译语言
    room_name = ctx.room.name
    logger.info(f"🏠 Agent joining room: {room_name}")
    
    # 根据房间名称确定翻译类型和提示词
    if room_name == ROOM_ZH:
        # 中文原音房间 - 不需要翻译
        agent_prompt = "你是一个中文语音助手，直接播放原始中文语音，无需翻译。"
        agent = TranslationAgent("zh", agent_prompt)
    elif room_name == ROOM_KR:
        # 韩文翻译房间
        agent = TranslationAgent("kr", KR_PROMPT)
    elif room_name == ROOM_VN:
        # 越南文翻译房间
        agent = TranslationAgent("vn", VN_PROMPT)
    else:
        # 默认中文房间
        agent_prompt = "你是一个中文语音助手。"
        agent = TranslationAgent("zh", agent_prompt)
    
    # 创建AgentSession - 按照官方文档的STT-LLM-TTS管道
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
    
    # 启动会话
    await session.start(
        room=ctx.room,
        agent=agent
    )
    
    # 连接到房间
    await ctx.connect()
    
    # 生成初始回复
    if room_name == ROOM_ZH:
        await session.generate_reply(
            instructions="欢迎来到中文原音房间。"
        )
    elif room_name == ROOM_KR:
        await session.generate_reply(
            instructions="欢迎来到韩文翻译房间，我会将中文翻译成韩文。"
        )
    elif room_name == ROOM_VN:
        await session.generate_reply(
            instructions="欢迎来到越南文翻译房间，我会将中文翻译成越南文。"
        )
    
    logger.info(f"✅ Agent started for room {room_name}")

if __name__ == "__main__":
    # 验证必要的API密钥
    if not GROQ_API_KEY:
        logger.error("❌ GROQ_API_KEY environment variable is required")
        exit(1)
    
    if not DEEPGRAM_API_KEY:
        logger.error("❌ DEEPGRAM_API_KEY environment variable is required")
        exit(1)
        
    if not CARTESIA_API_KEY:
        logger.error("❌ CARTESIA_API_KEY environment variable is required")
        exit(1)
    
    logger.info("🚀 Starting LiveKit Agent with Groq LLM")
    logger.info(f"支持的房间:")
    logger.info(f"  - 中文原音: {ROOM_ZH}")
    logger.info(f"  - 韩文翻译: {ROOM_KR}")
    logger.info(f"  - 越南文翻译: {ROOM_VN}")
    
    # 运行Agent
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    ) 
