import logging
import openai
from livekit.agents import llm
from livekit import rtc
from translation_prompts import (
    SYSTEM_PROMPT_CHINESE, 
    SYSTEM_PROMPT_ENGLISH, 
    SYSTEM_PROMPT_SPANISH, 
    SYSTEM_PROMPT_FRENCH
)

logger = logging.getLogger(__name__)

async def create_session(
    target_language: str = "zh",
    source_language: str = "en",
    api_key: str = None,
    model: str = "gpt-4o-realtime-preview"
) -> llm.RealtimeSession:
    """
    创建OpenAI Realtime会话用于实时翻译
    
    Args:
        target_language: 目标语言代码 (zh, en, es, fr)
        source_language: 源语言代码 (zh, en, es, fr) 
        api_key: OpenAI API密钥
        model: 使用的模型名称
        
    Returns:
        RealtimeSession: 配置好的实时会话
    """
    try:
        logger.info(f"🔧 Creating session for {source_language} -> {target_language}")
        
        # 选择合适的提示词
        prompt_map = {
            "zh": SYSTEM_PROMPT_CHINESE,
            "en": SYSTEM_PROMPT_ENGLISH, 
            "es": SYSTEM_PROMPT_SPANISH,
            "fr": SYSTEM_PROMPT_FRENCH
        }
        
        prompt = prompt_map.get(target_language, SYSTEM_PROMPT_ENGLISH)
        logger.info(f"📝 Using prompt for target language: {target_language}")
        
        # 按照LiveKit官方文档创建RealtimeModel
        # 参考: https://docs.livekit.io/reference/python/livekit/plugins/openai/realtime/realtime_model.html
        realtime_model = openai.realtime.RealtimeModel(
            instructions=prompt,
            model=model,
            voice="alloy",
            temperature=0.8,
            modalities=["text", "audio"],
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            api_key=api_key
        )
        
        logger.info(f"✅ RealtimeModel created successfully with model: {model}")
        
        # 创建会话
        session = realtime_model.session()
        logger.info("✅ RealtimeSession created successfully")
        
        return session
        
    except Exception as e:
        logger.error(f"❌ RealtimeModel creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {str(e)}")
        raise 
