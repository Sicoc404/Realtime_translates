import logging
import os
from livekit.agents import AgentSession
from livekit.plugins import groq
from translation_prompts import (
    SYSTEM_PROMPT_CHINESE, 
    SYSTEM_PROMPT_ENGLISH, 
    SYSTEM_PROMPT_SPANISH, 
    SYSTEM_PROMPT_FRENCH,
    KR_PROMPT,
    VN_PROMPT
)

logger = logging.getLogger(__name__)

def create_agent_session():
    """
    创建Agent会话，用于处理翻译请求
    按照LiveKit官方文档的标准方式
    
    Returns:
        dict: 包含翻译器的字典
    """
    try:
        logger.info("🔧 创建Agent会话...")
        
        # 获取环境变量
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("未设置GROQ_API_KEY环境变量")
        
        # 创建Groq LLM实例用于韩文翻译
        logger.info("创建韩文翻译器...")
        kr_translator = groq.LLM(
            model="llama3-8b-8192"
        )
        logger.info("✅ 韩文翻译器创建成功")
        
        # 创建Groq LLM实例用于越南文翻译
        logger.info("创建越南文翻译器...")
        vn_translator = groq.LLM(
            model="llama3-8b-8192"
        )
        logger.info("✅ 越南文翻译器创建成功")
        
        # 返回翻译器字典（简化版Agent会话）
        logger.info("创建Agent会话字典...")
        agent_session = {
            "kr_translator": kr_translator,
            "vn_translator": vn_translator
        }
        
        logger.info("✅ Agent会话创建成功")
        return agent_session
        
    except Exception as e:
        logger.error(f"❌ Agent会话创建失败: {e}")
        logger.error(f"📋 错误详情: {type(e).__name__}: {e}")
        raise e 
