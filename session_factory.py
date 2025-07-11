import logging
from livekit.agents import llm
# ⚙️ Use RealtimeModel from livekit.plugins.openai per docs
from livekit.plugins import openai
from livekit import rtc
from translation_prompts import (
    SYSTEM_PROMPT_CHINESE, 
    SYSTEM_PROMPT_ENGLISH, 
    SYSTEM_PROMPT_SPANISH, 
    SYSTEM_PROMPT_FRENCH,
    KR_PROMPT,
    VN_PROMPT
)

logger = logging.getLogger(__name__)

async def create_session(
    lang_code: str,
    prompt: str,
    room_name: str,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    openai_api_key: str,
    text_callback=None,
    model: str = "gpt-4o-realtime-preview"
) -> llm.RealtimeSession:
    """
    创建OpenAI Realtime会话用于实时翻译
    
    Args:
        lang_code: 语言代码 (zh, kr, vn, en, es, fr)
        prompt: 翻译提示词
        room_name: LiveKit房间名称
        livekit_url: LiveKit服务器URL
        api_key: LiveKit API密钥
        api_secret: LiveKit API密钥
        openai_api_key: OpenAI API密钥
        text_callback: 文本回调函数
        model: 使用的模型名称
        
    Returns:
        RealtimeSession: 配置好的实时会话
    """
    try:
        logger.info(f"🔧 Creating session for language: {lang_code}")
        logger.info(f"🏠 Room: {room_name}")
        logger.info(f"📝 Using prompt: {prompt[:50]}...")
        
        # ⚙️ 按照LiveKit官方文档创建RealtimeModel
        # 参考: https://docs.livekit.io/agents/integrations/realtime/openai/
        # RealtimeModel() 构造函数不接受参数，系统提示通过Agent设置
        realtime_model = openai.realtime.RealtimeModel()
        
        # 创建会话
        session = realtime_model.session()
        
        logger.info("✅ RealtimeModel created successfully")
        logger.info(f"🎯 Session created for {lang_code} translation")
        
        return session
        
    except Exception as e:
        logger.error(f"❌ RealtimeModel creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {e}")
        raise e 
