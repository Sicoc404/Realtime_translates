import asyncio
import os
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any
import pathlib

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from livekit import agents
from livekit.agents import Worker, WorkerOptions  # ⚙️ Updated import for livekit v1.x
from livekit.agents.cli import run_app  # ⚙️ import run_app from cli
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

# ⚙️ 全局变量存储会话状态
translation_sessions = {}
is_translation_running = False
worker_task = None

# ⚙️ FastAPI lifespan setup for background worker
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ⚙️ Startup: launch background worker
    global worker_task
    worker_task = asyncio.create_task(run_worker())
    print("FastAPI 服务启动中...")
    print("正在后台启动翻译服务...")
    
    yield  # 服务运行中...
    
    # ⚙️ Shutdown: cleanup resources
    print("正在关闭翻译服务...")
    await shutdown_translation_service()
    if worker_task and not worker_task.done():
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    print("翻译服务已关闭")

# ⚙️ Initialize FastAPI with lifespan
app = FastAPI(
    title="Real-time Translation Service", 
    version="1.0.0",
    lifespan=lifespan
)

# ⚙️ Mount static files
static_dir = pathlib.Path(__file__).parent / "static"
# 确保静态文件目录存在
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ⚙️ Health and UI routes
@app.get("/", response_class=HTMLResponse)
async def homepage():
    """根路由，返回index.html页面"""
    # ⚙️ Serving custom index.html
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 如果找不到index.html，返回一个简单的HTML响应
        return """
        <html>
            <head>
                <title>实时翻译服务</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                        line-height: 1.6;
                    }
                    h1 {
                        color: #4a5568;
                        border-bottom: 2px solid #e2e8f0;
                        padding-bottom: 10px;
                    }
                    .status {
                        background-color: #f0fff4;
                        border-left: 4px solid #48bb78;
                        padding: 12px;
                        margin: 20px 0;
                    }
                    a {
                        color: #4299e1;
                        text-decoration: none;
                    }
                    a:hover {
                        text-decoration: underline;
                    }
                    .links {
                        margin-top: 30px;
                    }
                    .links a {
                        margin-right: 15px;
                    }
                </style>
            </head>
            <body>
                <h1>实时翻译服务 ✔️</h1>
                <div class="status">
                    <p>🟢 实时翻译服务运行中</p>
                </div>
                <p>
                    这是一个基于LiveKit的实时语音翻译系统，可以将中文语音翻译成韩文和越南文。
                </p>
                <div class="links">
                    <a href="/health">健康检查</a> | 
                    <a href="/status">服务状态</a>
                </div>
            </body>
        </html>
        """

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

# ⚙️ Startup background worker
async def run_worker():
    """在后台运行LiveKit Worker"""
    try:
        # 创建WorkerOptions
        opts = WorkerOptions(
            entrypoint_function,  # 传入口函数作为第一个位置参数
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            ws_url=LIVEKIT_URL  # 使用ws_url而不是host
        )
        
        # 启动翻译服务
        await entrypoint_function()
        
        # 注意：这里不直接调用run_app(opts)，因为它会阻塞当前协程
        # 我们已经在entrypoint_function中实现了主要逻辑
        
    except Exception as e:
        print(f"启动翻译服务失败: {e}")
        raise

async def entrypoint_function():
    """
    LiveKit Worker 入口点函数
    此函数包含主要应用逻辑
    """
    # 调用主函数
    await main()

async def main():
    """主要的音频翻译处理逻辑"""
    global is_translation_running, translation_sessions
    
    try:
        # 设置字幕处理器
        kr_subtitle_handler, vn_subtitle_handler = setup_subtitle_handlers()
        
        # 启动 FastAPI 服务器（如果安装了FastAPI）
        # 注意：我们不再需要在这里启动FastAPI，因为它已经作为主应用启动
        # start_api()
        
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
            openai_api_key=OPENAI_API_KEY,
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
            openai_api_key=OPENAI_API_KEY,
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
            openai_api_key=OPENAI_API_KEY,
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
        await shutdown_translation_service()

async def shutdown_translation_service():
    """关闭所有翻译会话"""
    global is_translation_running, translation_sessions
    
    if translation_sessions:
        print("正在关闭翻译会话...")
        await asyncio.gather(
            *[session.close() for session in translation_sessions.values()],
            return_exceptions=True
        )
        translation_sessions.clear()
    
    is_translation_running = False

# ⚙️ Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.getenv("PORT", "10000")),
        reload=False  # 避免在生产环境中使用reload
    )
