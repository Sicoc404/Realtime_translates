import asyncio
import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Worker, WorkerOptions  # ⚙️ Updated import for livekit v1.x
from livekit.agents.cli import run_app  # ⚙️ import run_app from cli
from livekit.plugins import openai  # ⚙️ Updated import for livekit v1.x
# ⚙️ Removed audio plugin import — not required in livekit-agents v1.x

# ⚙️ Render health check setup
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
import threading

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

# ⚙️ Render health check setup - FastAPI应用实例
app = FastAPI(title="Real-time Translation Service", version="1.0.0")

# ⚙️ Render health check setup - 全局变量存储会话状态
translation_sessions = {}
is_translation_running = False

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return JSONResponse(
        status_code=200,
        content={"status": "ok"}
    )

@app.get("/status")
async def get_status():
    """获取翻译服务状态"""
    return JSONResponse(
        status_code=200,
        content={
            "translation_running": is_translation_running,
            "active_sessions": len(translation_sessions),
            "rooms": {
                "chinese": ROOM_ZH,
                "korean": ROOM_KR,
                "vietnamese": ROOM_VN
            }
        }
    )

async def entrypoint_function():
    """
    LiveKit Worker 入口点函数
    此函数作为 WorkerOptions 的第一个位置参数，包含主要应用逻辑
    """
    # 调用主函数
    await main()

async def main():
    """主要的音频翻译处理逻辑"""
    global is_translation_running, translation_sessions
    
    try:
        # ⚙️ Worker will be created by run_app in the main block
        
        # 设置字幕处理器
        kr_subtitle_handler, vn_subtitle_handler = setup_subtitle_handlers()
        
        # 启动 FastAPI 服务器（如果安装了FastAPI）
        start_api()
        
        # 创建三个不同的会话
        print("正在启动翻译会话...")
        
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
        
        # 存储会话到全局变量
        translation_sessions = {
            "zh": zh_session,
            "kr": kr_session,
            "vn": vn_session
        }
        
        is_translation_running = True
        
        print("所有翻译会话已启动...")
        print(f"中文原音广播到房间: {ROOM_ZH}")
        print(f"韩文翻译广播到房间: {ROOM_KR}")
        print(f"越南文翻译广播到房间: {ROOM_VN}")
        print("翻译服务正在后台运行...")
        
        # 保持会话运行
        await asyncio.gather(
            zh_session.wait_until_done(),
            kr_session.wait_until_done(),
            vn_session.wait_until_done()
        )
        
    except Exception as e:
        print(f"翻译服务启动失败: {e}")
        is_translation_running = False
    finally:
        # 关闭所有会话
        if translation_sessions:
            print("正在关闭翻译服务...")
            await asyncio.gather(
                *[session.close() for session in translation_sessions.values()],
                return_exceptions=True
            )
            translation_sessions.clear()
        
        is_translation_running = False
        print("翻译服务已关闭")

# ⚙️ Render health check setup - 后台任务启动翻译服务
async def start_translation_service():
    """后台任务：启动翻译服务"""
    try:
        # ⚙️ Using run_app(opts) from cli module for livekit v1.x compatibility
        opts = WorkerOptions(
            entrypoint_function,  # 传入口函数作为第一个位置参数
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            ws_url=LIVEKIT_URL  # 使用ws_url而不是host
        )
        
        # 在单独的线程中运行 LiveKit worker
        def run_worker():
            try:
                run_app(opts)
            except Exception as e:
                print(f"LiveKit Worker 运行错误: {e}")
        
        # 启动 worker 线程
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        worker_thread.start()
        
    except Exception as e:
        print(f"启动翻译服务失败: {e}")

@app.on_event("startup")
async def startup_event():
    """应用启动时的事件处理"""
    print("FastAPI 服务启动中...")
    print("正在后台启动翻译服务...")
    
    # 在后台启动翻译服务
    asyncio.create_task(start_translation_service())

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的事件处理"""
    global is_translation_running, translation_sessions
    
    print("正在关闭翻译服务...")
    
    # 关闭所有翻译会话
    if translation_sessions:
        for session in translation_sessions.values():
            try:
                await session.close()
            except Exception as e:
                print(f"关闭会话时出错: {e}")
    
    translation_sessions.clear()
    is_translation_running = False
    print("翻译服务已关闭")

# ⚙️ Render health check setup - 主程序入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "5000")),
        reload=False  # 避免在生产环境中使用reload
    )
