from livekit import agents
from livekit.agents import AgentContext, AgentSession  # ⚙️ Updated import for livekit v1.x
from livekit.plugins.audio import AudioCapture, AudioBroadcast
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
    # 创建会话上下文
    context = AgentContext(
        url=livekit_url,
        api_key=api_key,
        api_secret=api_secret,
        identity=f"translator_{lang_code}",
        name=f"{lang_code.upper()} Translator"
    )
    
    # 注册音频捕获插件 - 捕获用户的中文语音
    audio_capture = AudioCapture()
    
    # 注册音频广播插件 - 广播翻译后的语音到房间
    audio_broadcast = AudioBroadcast(room_name=room_name)
    
    # ⚙️ 使用新版API创建OpenAI实时模型
    realtime_model = openai.realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",  # ⚙️ 更新为最新模型名称
        audio_input=audio_capture,
        audio_output=audio_broadcast,
        text_callback=text_callback,  # 如果提供了回调，处理生成的文本
        system=prompt,  # 使用传入的提示词
        turn_detection="server_vad",  # 使用服务器端语音活动检测
        api_key=openai_api_key  # ⚙️ 添加API密钥参数
    )
    
    # ⚙️ 新版API直接将插件传递给AgentSession构造函数
    session = AgentSession(
        context=context,
        llm=realtime_model,
        plugins=[audio_capture, audio_broadcast]
    )
    
    # 启动会话
    await session.start()
    
    print(f"{lang_code.upper()} 翻译会话已创建并启动")
    return session 
