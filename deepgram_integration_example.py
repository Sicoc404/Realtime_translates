import asyncio
import logging
import os
from livekit.agents import llm
import openai

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
        
        # 创建RealtimeModel - 使用与session_factory.py相同的方式
        realtime_model = openai.realtime.RealtimeModel(
            instructions="You are a helpful AI assistant that can translate between languages.",
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
        logger.error(f"❌ Deepgram Realtime session creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {str(e)}")
        raise

async def main():
    """测试函数"""
    try:
        session = await create_deepgram_realtime_session()
        logger.info("🎉 Deepgram + OpenAI Realtime session created successfully!")
        
        # 在这里可以添加更多的测试逻辑
        # 例如: 测试音频输入/输出
        
        # 清理
        if hasattr(session, 'aclose'):
            await session.aclose()
            logger.info("✅ Session closed successfully")
            
    except Exception as e:
        logger.error(f"❌ Main function failed: {e}")

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    asyncio.run(main()) 
