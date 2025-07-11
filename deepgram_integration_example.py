import asyncio
import logging
import os
from livekit.agents import llm
# ⚙️ Use RealtimeModel from livekit.plugins.openai per docs
from livekit.plugins import openai

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
        # 参考: https://docs.livekit.io/agents/integrations/realtime/openai/
        # RealtimeModel() 构造函数不接受参数，系统提示通过Agent设置
        realtime_model = openai.realtime.RealtimeModel()
        
        # 创建会话
        session = realtime_model.session()
        
        logger.info("✅ Deepgram + OpenAI Realtime session created successfully")
        return session
        
    except Exception as e:
        logger.error(f"❌ Deepgram Realtime session creation failed: {e}")
        logger.error(f"📋 Error details: {type(e).__name__}: {e}")
        raise e

# 示例使用
async def main():
    """
    主函数示例
    """
    try:
        session = await create_deepgram_realtime_session()
        logger.info("🎉 Session ready for use")
        
        # 这里可以添加更多的会话配置和使用逻辑
        
    except Exception as e:
        logger.error(f"❌ Main function failed: {e}")

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 运行主函数
    asyncio.run(main()) 
