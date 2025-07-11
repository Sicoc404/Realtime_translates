import asyncio
import logging
import os
from livekit.agents import llm
# ⚙️ Use RealtimeModel from livekit.plugins.openai.realtime per docs
from livekit.plugins.openai.realtime import RealtimeModel

logger = logging.getLogger(__name__)

async def create_deepgram_realtime_session():
    """
    创建使用Deepgram STT的OpenAI Realtime会话示例
    """
    try:
        logger.info("🔧 Creating Deepgram + OpenAI Realtime session")
        
        # 获取API密钥
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # ⚙️ 按照LiveKit官方文档创建RealtimeModel
        # 参考: https://docs.livekit.io/reference/python/livekit/plugins/openai/realtime/realtime_model.html
        realtime_model = RealtimeModel(
            instructions="You are a helpful AI assistant that can translate between languages.",  # ⚙️ system prompt
            model="gpt-4o-realtime-preview",
            voice="alloy",
            temperature=0.8,
            modalities=["text", "audio"],
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            api_key=openai_api_key
        )
        
        logger.info("✅ RealtimeModel created successfully")
        
        # 创建会话
        session = realtime_model.session()
        logger.info("✅ RealtimeSession created successfully")
        
        return session
        
    except Exception as e:
        logger.error(f"❌ Deepgram RealtimeModel creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(create_deepgram_realtime_session()) 
