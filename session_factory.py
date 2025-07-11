import logging
from livekit.agents import llm
# ⚙️ Use Groq LLM from livekit.plugins.groq per docs
from livekit.plugins import groq
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

def create_groq_llm(
    lang_code: str,
    prompt: str,
    room_name: str,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    groq_api_key: str,
    text_callback=None,
    model: str = "llama3-8b-8192"
) -> groq.LLM:
    """
    创建Groq LLM用于实时翻译
    
    Args:
        lang_code: 语言代码 (zh, kr, vn, en, es, fr)
        prompt: 翻译提示词
        room_name: LiveKit房间名称
        livekit_url: LiveKit服务器URL
        api_key: LiveKit API密钥
        api_secret: LiveKit API密钥
        groq_api_key: Groq API密钥
        text_callback: 文本回调函数
        model: 使用的模型名称
        
    Returns:
        groq.LLM: 配置好的Groq LLM
    """
    try:
        logger.info(f"🔧 Creating Groq LLM for language: {lang_code}")
        logger.info(f"🏠 Room: {room_name}")
        logger.info(f"📝 Using prompt: {prompt[:50]}...")
        
        # ⚙️ 按照LiveKit官方文档创建Groq LLM
        # 参考: https://docs.livekit.io/agents/integrations/groq/
        groq_llm = groq.LLM(
            model=model,
            api_key=groq_api_key
        )
        
        logger.info("✅ Groq LLM created successfully")
        logger.info(f"🎯 LLM ready for {lang_code} translation")
        
        return groq_llm
        
    except Exception as e:
        logger.error(f"❌ Groq LLM creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {e}")
        raise e

# 为了向后兼容，保留原函数名但使用Groq LLM
def create_realtime_model(
    lang_code: str,
    prompt: str,
    room_name: str,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    openai_api_key: str,  # 保留参数名以兼容现有代码
    text_callback=None,
    model: str = "llama3-8b-8192"
) -> groq.LLM:
    """
    创建Groq LLM用于实时翻译 (向后兼容函数)
    
    注意: 这个函数现在返回Groq LLM而不是OpenAI RealtimeModel
    """
    # 将openai_api_key参数重新映射为groq_api_key
    return create_groq_llm(
        lang_code=lang_code,
        prompt=prompt,
        room_name=room_name,
        livekit_url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        groq_api_key=openai_api_key,  # 重新映射参数
        text_callback=text_callback,
        model=model
    )

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
    model: str = "llama3-8b-8192"
) -> groq.LLM:
    """
    创建Groq LLM用于实时翻译 (向后兼容)
    
    注意: 这个函数现在返回Groq LLM而不是会话
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
