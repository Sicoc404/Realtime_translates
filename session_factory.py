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

def create_realtime_model(
    lang_code: str,
    prompt: str,
    room_name: str,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    openai_api_key: str,
    text_callback=None,
    model: str = "gpt-4o-realtime-preview"
) -> openai.realtime.RealtimeModel:
    """
    创建OpenAI RealtimeModel用于实时翻译
    
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
        RealtimeModel: 配置好的实时模型
    """
    try:
        logger.info(f"🔧 Creating RealtimeModel for language: {lang_code}")
        logger.info(f"🏠 Room: {room_name}")
        logger.info(f"📝 Using prompt: {prompt[:50]}...")
        
        # ⚙️ 按照LiveKit官方文档创建RealtimeModel
        # 参考: https://docs.livekit.io/agents/integrations/realtime/openai/
        # RealtimeModel() 构造函数不接受参数，系统提示通过Agent设置
        realtime_model = openai.realtime.RealtimeModel()
        
        logger.info("✅ RealtimeModel created successfully")
        logger.info(f"🎯 Model ready for {lang_code} translation")
        
        return realtime_model
        
    except Exception as e:
        logger.error(f"❌ RealtimeModel creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {e}")
        raise e

# 保持向后兼容的别名
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
) -> openai.realtime.RealtimeModel:
    """
    创建OpenAI Realtime会话用于实时翻译 (向后兼容)
    
    注意: 这个函数现在返回RealtimeModel而不是会话
    """
    return create_realtime_model(
        lang_code=lang_code,
        prompt=prompt,
        room_name=room_name,
        livekit_url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        openai_api_key=openai_api_key,
        text_callback=text_callback,
        model=model
    ) 
