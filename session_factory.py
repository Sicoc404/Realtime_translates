from livekit import agents
from livekit.agents import AgentSession  # ⚙️ Removed AgentContext import for livekit v1.x compatibility
# ⚙️ Removed audio plugin import — not required in livekit-agents v1.x
from livekit.plugins import openai  # ⚙️ Updated import for livekit v1.x
from typing import Optional, Callable

async def create_session(
    lang_code: str,
    prompt: str,
    room_name: str,
    livekit_url: str,
    api_key: str, 
    api_secret: str,
    openai_api_key: str,  # ⚙️ 添加OpenAI API密钥参数
    text_callback: Optional[Callable[[str], None]] = None
) -> agents.AgentSession:
    """
    创建一个语言翻译会话
    
    参数:
        lang_code: 目标语言代码 (zh, kr, vn)
        prompt: 翻译系统的提示词
        room_name: LiveKit房间名称
        livekit_url: LiveKit服务器URL
        api_key: LiveKit API密钥
        api_secret: LiveKit API密钥
        openai_api_key: OpenAI API密钥
        text_callback: 处理生成文本的回调函数
    
    返回:
        agents.AgentSession: LiveKit代理会话
    """
    # ⚙️ 创建会话参数，不再使用AgentContext
    connection_info = {
        "url": livekit_url,
        "api_key": api_key,
        "api_secret": api_secret,
        "identity": f"translator_{lang_code}",
        "name": f"{lang_code.upper()} Translator"
    }
    
    # ⚙️ 使用新版API创建OpenAI实时模型，严格按照官方文档签名
    # ⚙️ Use instructions instead of system per RealtimeModel constructor signature
    realtime_model = openai.realtime.RealtimeModel(
        instructions=prompt,  # 系统指令，替换原来的system参数
        voice="alloy",  # 语音模型
        temperature=0.8,  # 温度参数
        api_key=openai_api_key  # OpenAI API密钥
    )
    
    # ⚙️ 创建LiveKit代理会话
    session = AgentSession(
        url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        identity=f"translator_{lang_code}",
        name=f"{lang_code.upper()} Translator"
    )
    
    # 设置文本回调（如果提供）
    if text_callback:
        realtime_model.text_callback = text_callback
    
    # 将模型添加到会话
    session.add_model(realtime_model)
    
    # 启动会话
    await session.start()
    
    # 连接到指定房间
    await session.connect(room_name)
    
    print(f"{lang_code.upper()} 翻译会话已创建并启动")
    return session 
