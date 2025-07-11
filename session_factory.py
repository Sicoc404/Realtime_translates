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
    
    # ⚙️ 创建OpenAI实时模型 - 使用最简化的参数避免兼容性问题
    # ⚙️ CRITICAL: Use instructions instead of system per RealtimeModel constructor signature
    try:
        realtime_model = openai.realtime.RealtimeModel(
            instructions=prompt  # 只使用最基本的instructions参数
        )
        print(f"✅ RealtimeModel created successfully for {lang_code}")
    except Exception as e:
        print(f"❌ RealtimeModel creation failed: {e}")
        raise
    
    # ⚙️ 创建LiveKit代理会话
    try:
        session = AgentSession(
            url=livekit_url,
            api_key=api_key,
            api_secret=api_secret,
            identity=f"translator_{lang_code}",
            name=f"{lang_code.upper()} Translator"
        )
        print(f"✅ AgentSession created successfully for {lang_code}")
    except Exception as e:
        print(f"❌ AgentSession creation failed: {e}")
        raise
    
    # 设置OpenAI API密钥（如果模型支持）
    if hasattr(realtime_model, 'api_key'):
        realtime_model.api_key = openai_api_key
    
    # 设置文本回调（如果提供且模型支持）
    if text_callback and hasattr(realtime_model, 'text_callback'):
        realtime_model.text_callback = text_callback
    
    # 设置语音参数（如果模型支持）
    if hasattr(realtime_model, 'voice'):
        realtime_model.voice = "alloy"
    
    # 设置温度参数（如果模型支持）
    if hasattr(realtime_model, 'temperature'):
        realtime_model.temperature = 0.8
    
    # 将模型添加到会话（如果会话支持）
    if hasattr(session, 'add_model'):
        session.add_model(realtime_model)
    
    # 启动会话
    try:
        await session.start()
        print(f"✅ Session started successfully for {lang_code}")
    except Exception as e:
        print(f"❌ Session start failed: {e}")
        raise
    
    # 连接到指定房间（如果会话支持）
    try:
        if hasattr(session, 'connect'):
            await session.connect(room_name)
            print(f"✅ Connected to room {room_name} for {lang_code}")
    except Exception as e:
        print(f"❌ Room connection failed: {e}")
        # 不抛出异常，因为这可能不是必需的
    
    print(f"🎉 {lang_code.upper()} 翻译会话已创建并启动")
    return session 
