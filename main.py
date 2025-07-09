import asyncio
import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Worker  # ⚙️ Updated import for livekit v1.x
from livekit.plugins import openai  # ⚙️ Updated import for livekit v1.x

from session_factory import create_session
from translation_prompts import KR_PROMPT, VN_PROMPT
from console_output import setup_subtitle_handlers, start_api

# 加载环境变量
load_dotenv()

# LiveKit 配置
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

# OpenAI API 密钥
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 房间名称
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间
ROOM_VN = "room_vn"  # 越南文翻译房间

async def main():
    # ⚙️ Updated worker initialization for livekit v1.x
    # 初始化工作线程，OpenAI API密钥在session创建时提供
    worker = Worker()
    await worker.start()
    
    # 设置字幕处理器
    kr_subtitle_handler, vn_subtitle_handler = setup_subtitle_handlers()
    
    # 启动 FastAPI 服务器（如果安装了FastAPI）
    start_api()
    
    # 创建三个不同的会话
    # 1. 中文原音会话 - 仅用于广播原始语音
    zh_session = await create_session(
        lang_code="zh",
        prompt="只需播放原始中文语音，无需翻译。",
        room_name=ROOM_ZH,
        livekit_url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        openai_api_key=OPENAI_API_KEY,  # ⚙️ 传递OpenAI API密钥
        text_callback=None  # 原音不需要文本回调
    )
    
    # 2. 中文到韩文翻译会话
    kr_session = await create_session(
        lang_code="kr",
        prompt=KR_PROMPT,
        room_name=ROOM_KR,
        livekit_url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        openai_api_key=OPENAI_API_KEY,  # ⚙️ 传递OpenAI API密钥
        text_callback=kr_subtitle_handler
    )
    
    # 3. 中文到越南文翻译会话
    vn_session = await create_session(
        lang_code="vn",
        prompt=VN_PROMPT,
        room_name=ROOM_VN,
        livekit_url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        openai_api_key=OPENAI_API_KEY,  # ⚙️ 传递OpenAI API密钥
        text_callback=vn_subtitle_handler
    )
    
    print("所有翻译会话已启动...")
    print(f"中文原音广播到房间: {ROOM_ZH}")
    print(f"韩文翻译广播到房间: {ROOM_KR}")
    print(f"越南文翻译广播到房间: {ROOM_VN}")
    print("按 Ctrl+C 停止服务...")
    
    try:
        # 保持会话运行
        await asyncio.gather(
            zh_session.wait_until_done(),
            kr_session.wait_until_done(),
            vn_session.wait_until_done()
        )
    except KeyboardInterrupt:
        print("正在关闭翻译服务...")
    finally:
        # 关闭所有会话
        await asyncio.gather(
            zh_session.close(),
            kr_session.close(),
            vn_session.close()
        )
        
        # ⚙️ 关闭worker
        await worker.stop()
        
        print("翻译服务已关闭")

if __name__ == "__main__":
    asyncio.run(main()) 
