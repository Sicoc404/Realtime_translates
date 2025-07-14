import logging
import os
# 移除对livekit.agents的依赖
# from livekit.agents import llm, AgentSession
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

# 创建自定义的AgentSession类，替代livekit.agents.AgentSession
class AgentSession:
    """
    自定义Agent会话类，用于管理翻译器
    """
    def __init__(self, kr_translator=None, vn_translator=None):
        """
        初始化Agent会话
        
        Args:
            kr_translator: 韩文翻译器
            vn_translator: 越南文翻译器
        """
        self.kr_translator = kr_translator
        self.vn_translator = vn_translator
        logger.info("✅ 自定义AgentSession创建成功")

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

# 创建自定义的GroqTranslator类，简化Groq LLM的使用
class GroqTranslator:
    """
    Groq翻译器，封装Groq LLM的翻译功能
    """
    def __init__(self, api_key, system_prompt, model="llama3-8b-8192"):
        """
        初始化Groq翻译器
        
        Args:
            api_key: Groq API密钥
            system_prompt: 系统提示词
            model: 使用的模型名称
        """
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model = model
        
        # 初始化Groq客户端
        import groq
        self.client = groq.Groq(api_key=api_key)
        logger.info(f"✅ Groq翻译器初始化成功，模型: {model}")
    
    def generate(self, text):
        """
        生成翻译
        
        Args:
            text: 待翻译的文本
            
        Returns:
            str: 翻译结果
        """
        try:
            # 构建提示词
            prompt = f"{self.system_prompt}\n\n原文: {text}\n\n翻译:"
            
            # 调用Groq API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000,
                temperature=0.3,
            )
            
            # 提取翻译结果
            translation = completion.choices[0].message.content
            return translation.strip()
            
        except Exception as e:
            logger.error(f"❌ 翻译失败: {e}")
            return f"[翻译错误: {str(e)}]"

def create_agent_session() -> AgentSession:
    """
    创建Agent会话，用于处理翻译请求
    
    Returns:
        AgentSession: 配置好的Agent会话
    """
    try:
        logger.info("🔧 创建Agent会话...")
        
        # 获取环境变量
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("未设置GROQ_API_KEY环境变量")
        
        # 创建翻译器实例
        groq_llm_kr = GroqTranslator(
            api_key=groq_api_key,
            system_prompt=KR_PROMPT,
            model="llama3-8b-8192"
        )
        
        groq_llm_vn = GroqTranslator(
            api_key=groq_api_key,
            system_prompt=VN_PROMPT,
            model="llama3-8b-8192"
        )
        
        # 创建Agent会话
        agent_session = AgentSession(
            kr_translator=groq_llm_kr,
            vn_translator=groq_llm_vn
        )
        
        logger.info("✅ Agent会话创建成功")
        return agent_session
        
    except Exception as e:
        logger.error(f"❌ Agent会话创建失败: {e}")
        logger.error(f"📋 错误详情: {type(e).__name__}: {e}")
        raise e 
