#!/usr/bin/env python3
"""
LiveKit Agent - 符合官方文档的实时翻译实现
使用STT-LLM-TTS管道架构
"""

import asyncio
import os
import logging
import socket
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions
from livekit.plugins import groq, deepgram, cartesia

from translation_prompts import KR_PROMPT, VN_PROMPT, JP_PROMPT

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别以获取更详细的日志
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("translation_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 房间名称定义 - 与前端保持一致
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间
ROOM_VN = "room_vn"  # 越南文翻译房间
ROOM_JP = "room_jp"  # 日文翻译房间

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

# 关键验证检查
if not all([GROQ_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY]):
    logger.error("❌ 缺少必要的API密钥配置")
    exit(1)


class TranslationAgent(Agent):
    """实时翻译Agent"""
    
    def __init__(self, lang_code: str, prompt: str):
        super().__init__(instructions=prompt)
        self.lang_code = lang_code
        self.prompt = prompt
        logger.info(f"🤖 创建翻译Agent: {lang_code}")
        
    async def on_message(self, message: str) -> str:
        """处理用户消息并返回翻译后的内容"""
        # 注入翻译指令到LLM上下文
        logger.debug(f"📥 收到STT消息: {message}")
        result = f"{self.prompt}\n\n{message}"
        logger.debug(f"📤 发送给LLM的内容: {result}")
        return result
        
    # 添加回调函数用于调试
    async def on_stt_result(self, result: str) -> None:
        """当STT结果可用时调用"""
        logger.info(f"🎤 STT结果: {result}")
        
    async def on_llm_result(self, result: str) -> None:
        """当LLM结果可用时调用"""
        logger.info(f"🧠 LLM结果: {result}")
        
    async def on_tts_result(self, audio_bytes: bytes) -> None:
        """当TTS结果可用时调用"""
        logger.info(f"🔊 TTS生成音频: {len(audio_bytes)} 字节")


# 自定义STT类，用于调试
class DebugDeepgramSTT(deepgram.STT):
    async def transcribe(self, audio_bytes):
        logger.debug(f"🎤 Deepgram STT接收音频: {len(audio_bytes)} 字节")
        try:
            result = await super().transcribe(audio_bytes)
            logger.debug(f"🎤 Deepgram STT结果: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Deepgram STT错误: {str(e)}")
            raise

# 自定义LLM类，用于调试
class DebugGroqLLM(groq.LLM):
    async def complete(self, prompt):
        logger.debug(f"🧠 Groq LLM接收提示词: {prompt}")
        try:
            result = await super().complete(prompt)
            logger.debug(f"🧠 Groq LLM结果: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Groq LLM错误: {str(e)}")
            raise

# 自定义TTS类，用于调试
class DebugCartesiaTTS(cartesia.TTS):
    async def synthesize(self, text):
        logger.debug(f"🔊 Cartesia TTS接收文本: {text}")
        try:
            result = await super().synthesize(text)
            logger.debug(f"🔊 Cartesia TTS生成音频: {len(result)} 字节")
            return result
        except Exception as e:
            logger.error(f"❌ Cartesia TTS错误: {str(e)}")
            raise


# 语言代码映射
LANGUAGE_CODE_MAP = {
    "zh": "zh",  # 中文
    "kr": "ko",  # 韩文
    "vn": "vi",  # 越南文
    "jp": "ja",  # 日文
}

# 声音ID映射 - 根据Cartesia支持的声音ID进行配置
VOICE_ID_MAP = {
    "zh": "a0e99841-438c-4a64-b679-ae501e7d6091",  # 中文声音ID
    "kr": "a0e99841-438c-4a64-b679-ae501e7d6091",  # 韩文声音ID
    "vn": "a0e99841-438c-4a64-b679-ae501e7d6091",  # 越南文声音ID
    "jp": "a0e99841-438c-4a64-b679-ae501e7d6091",  # 日文声音ID
}


async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent 入口点函数
    按照官方文档实现STT-LLM-TTS管道
    """
    
    # 必须先连接房间
    await ctx.connect()
    logger.info(f"✅ 已连接到房间: {ctx.room.name}")
    
    # 获取房间名称来确定翻译语言
    room_name = ctx.room.name
    logger.info(f"🏠 Agent加入房间: {room_name}")
    
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
    elif room_name == ROOM_JP:
        # 日文翻译房间
        agent = TranslationAgent("jp", JP_PROMPT)
    else:
        # 默认中文房间
        agent_prompt = "你是一个中文语音助手。"
        agent = TranslationAgent("zh", agent_prompt)
    
    # 创建AgentSession - 按照官方文档的STT-LLM-TTS管道
    try:
        # 确定目标语言的TTS配置
        tts_language = LANGUAGE_CODE_MAP.get(agent.lang_code, "zh")
        voice_id = VOICE_ID_MAP.get(agent.lang_code, "a0e99841-438c-4a64-b679-ae501e7d6091")
            
        logger.info(f"🔧 创建AgentSession用于房间: {room_name}")
        logger.info(f"🔧 翻译语言: {agent.lang_code} (TTS语言代码: {tts_language})")
        logger.info(f"🔧 提示词内容: {agent.prompt[:50]}...")
        logger.info(f"🔧 使用声音ID: {voice_id}")
        
        # 使用调试包装器
        session = AgentSession(
            stt=DebugDeepgramSTT(
                model="nova-2",
                language="zh",  # 中文语音识别
                interim_results=True,  # 启用中间结果
                endpointing=True,  # 启用端点检测
                vad_events=True,  # 启用语音活动检测事件
                punctuate=True,  # 启用标点
                diarize=False,  # 不需要说话人分离
            ),
            llm=DebugGroqLLM(
                model="llama3-8b-8192"
            ),
            tts=DebugCartesiaTTS(
                model="sonic-multilingual",
                voice=voice_id,  # 使用映射的声音ID
                language=tts_language  # 设置目标语言
            ),
        )
        
        logger.info(f"🔧 STT配置: 中文识别 | TTS配置: {tts_language}语音合成")
        
        # 启动会话
        await session.start(agent)
        logger.info(f"✅ AgentSession已启动，等待语音输入...")
        
        # 尝试启动麦克风
        try:
            logger.info("🎤 尝试启动麦克风...")
            await session.start_microphone()
            logger.info("✅ 麦克风已启动")
            
            # 注册RPC方法
            await ctx.register_rpc("start_translation", session.start_microphone)
            await ctx.register_rpc("stop_translation", session.stop_microphone)
            logger.info("✅ RPC方法已注册: start_translation, stop_translation")
            
            # 保持会话活跃
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ 启动麦克风失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"❌ 创建AgentSession失败: {str(e)}")
        import traceback
        logger.error(f"❌ 错误详情: {traceback.format_exc()}")
        raise


# DNS解析测试函数
def test_dns_resolution():
    """测试DNS解析是否正常工作"""
    try:
        logger.info(f"🔍 当前主机名: {socket.gethostname()}")
        logger.info(f"🔍 当前IP地址: {socket.gethostbyname(socket.gethostname())}")
        
        # 尝试解析一些常见域名
        test_domains = ["google.com", "microsoft.com", "github.com"]
        for domain in test_domains:
            try:
                ip = socket.gethostbyname(domain)
                logger.info(f"✅ 域名 {domain} 解析成功: {ip}")
            except Exception as e:
                logger.error(f"❌ 域名 {domain} 解析失败: {str(e)}")
        
        # 尝试解析LIVEKIT_URL
        if LIVEKIT_URL and "://" in LIVEKIT_URL:
            livekit_host = LIVEKIT_URL.replace("wss://", "").replace("https://", "").split("/")[0].split(":")[0]
            logger.info(f"🔍 尝试解析LiveKit主机: {livekit_host}")
            try:
                ip = socket.gethostbyname(livekit_host)
                logger.info(f"✅ LiveKit主机解析成功: {ip}")
            except Exception as e:
                logger.error(f"❌ LiveKit主机解析失败: {str(e)}")
                logger.error(f"⚠️ 请检查LIVEKIT_URL配置或网络连接")
    except Exception as e:
        logger.error(f"❌ DNS解析测试失败: {str(e)}")


# 主函数 - 用于测试
if __name__ == "__main__":
    # 测试DNS解析
    test_dns_resolution()
    
    try:
        # 确保LiveKit环境变量设置正确
        os.environ["LIVEKIT_URL"] = LIVEKIT_URL
        os.environ["LIVEKIT_API_KEY"] = LIVEKIT_API_KEY
        os.environ["LIVEKIT_API_SECRET"] = LIVEKIT_API_SECRET
        
        logger.info(f"🔍 LiveKit环境变量设置:")
        logger.info(f"  LIVEKIT_URL: {LIVEKIT_URL}")
        logger.info(f"  LIVEKIT_API_KEY: {LIVEKIT_API_KEY[:8]}...")
        logger.info(f"  LIVEKIT_API_SECRET: {LIVEKIT_API_SECRET[:8]}...")
        
        # 创建工作器选项，确保使用正确的环境变量
        worker_options = WorkerOptions(
            entrypoint_fnc=entrypoint,
            # 使用固定IP地址而不是主机名，避免DNS解析问题
            host="0.0.0.0",  # 绑定到所有网络接口
            port=0,  # 让系统自动分配端口
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            # 设置Agent名称以启用显式调度
            agent_name="translation-agent",
            # 开发模式设置
            load_threshold=float('inf'),  # 开发模式下不限制负载
        )
        
        logger.info(f"🚀 启动LiveKit Agent，连接到: {LIVEKIT_URL}")
        logger.info(f"🔧 工作器配置: host={worker_options.host}, port={worker_options.port}")
        logger.info(f"🔧 Agent名称: {worker_options.agent_name}")
        
        agents.cli.run_app(worker_options)
    except Exception as e:
        logger.error(f"❌ 启动LiveKit Agent失败: {str(e)}")
        import traceback
        logger.error(f"❌ 错误详情: {traceback.format_exc()}") 
