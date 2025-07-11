import asyncio
import os
import threading
import time  # 添加time模块
from contextlib import asynccontextmanager
from typing import Dict, Any
import pathlib
import logging  # 添加logging模块

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel

from livekit import agents
from livekit.agents import AgentSession, Agent, WorkerOptions, JobContext  # ⚙️ Updated imports
from livekit.agents.cli import run_app  # ⚙️ import run_app from cli
# ⚙️ Use RealtimeModel from livekit.plugins.openai per docs
from livekit.plugins import openai
from livekit.api import AccessToken, VideoGrants  # ⚙️ LiveKit token generation imports

from session_factory import create_realtime_model
from translation_prompts import KR_PROMPT, VN_PROMPT
from console_output import setup_subtitle_handlers, start_api

# 设置日志
logger = logging.getLogger("translation_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 加载环境变量
load_dotenv()

# LiveKit 配置
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "wss://your-livekit-server.com")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")  # 默认开发密钥
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")  # 默认开发密钥

# OpenAI API 密钥
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 房间名称
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间
ROOM_VN = "room_vn"  # 越南文翻译房间

# ⚙️ 全局变量存储会话状态
translation_sessions = {}
is_translation_running = False
worker_task = None
last_heartbeat = time.time()

# ⚙️ 创建Agent类
class TranslationAgent(Agent):
    """实时翻译Agent"""
    
    def __init__(self, lang_code: str, prompt: str):
        super().__init__(instructions=prompt)
        self.lang_code = lang_code
        self.prompt = prompt
        logger.info(f"🤖 Created TranslationAgent for {lang_code}")

# ⚙️ FastAPI lifespan setup for background worker
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ⚙️ Startup: launch background worker
    global worker_task
    worker_task = asyncio.create_task(run_worker())
    logger.info("FastAPI 服务启动中...")
    logger.info("正在后台启动翻译服务...")
    
    yield  # 服务运行中...
    
    # ⚙️ Shutdown: cleanup resources
    logger.info("⚙️ 正在关闭翻译服务...")
    await shutdown_translation_service()
    if worker_task and not worker_task.done():
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            logger.info("⚙️ Worker canceled")
        except Exception as e:
            logger.exception("Worker shutdown error: %s", e)
    logger.info("翻译服务已关闭")

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
        <head><title>Real-time Translation Service</title></head>
        <body>
            <h1>Real-time Translation Service</h1>
            <p>Translation service is running!</p>
            <p>Please check if index.html exists in the project directory.</p>
        </body>
        </html>
        """

# ⚙️ Health check endpoint
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": time.time()}

# ⚙️ Status endpoint with heartbeat
@app.get("/status")
async def get_status():
    """获取翻译服务状态"""
    global is_translation_running, last_heartbeat
    
    current_time = time.time()
    heartbeat_age = current_time - last_heartbeat
    worker_alive = heartbeat_age < 60  # 60秒内有心跳认为是活跃的
    
    return {
        "is_running": is_translation_running,
        "worker_alive": worker_alive,
        "last_heartbeat": last_heartbeat,
        "heartbeat_age": heartbeat_age,
        "rooms": {
            "zh": ROOM_ZH,
            "kr": ROOM_KR,
            "vn": ROOM_VN
        },
        "timestamp": current_time
    }

# ⚙️ Request models
class TokenRequest(BaseModel):
    roomName: str
    identity: str

# ⚙️ LiveKit token generation endpoint
@app.post("/token")
async def create_token(request: TokenRequest):
    """生成LiveKit房间Token"""
    try:
        # 创建AccessToken
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(request.identity) \
            .with_grants(VideoGrants(room_join=True, room=request.roomName)) \
            .to_jwt()
        
        return JSONResponse(
            status_code=200,
            content={"token": token}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"生成Token失败: {str(e)}"}
        )

# ⚙️ Worker heartbeat task
async def worker_heartbeat():
    """Worker心跳任务"""
    global last_heartbeat
    
    while True:
        try:
            last_heartbeat = time.time()
            await asyncio.sleep(30)  # 每30秒更新一次心跳
        except asyncio.CancelledError:
            logger.info("⚙️ Heartbeat task cancelled")
            break
        except Exception as e:
            logger.error(f"⚙️ Heartbeat error: {e}")
            await asyncio.sleep(30)

# ⚙️ Startup background worker
async def run_worker():
    """在后台运行LiveKit Worker"""
    global last_heartbeat
    
    logger.info("⚙️ Worker started")
    
    try:
        # 创建WorkerOptions
        opts = WorkerOptions(
            entrypoint_function,  # 传入口函数作为第一个位置参数
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            ws_url=LIVEKIT_URL  # 使用ws_url而不是host
        )
        
        # 启动心跳任务
        heartbeat_task = asyncio.create_task(worker_heartbeat())
        
        # 启动翻译服务
        await entrypoint_function()
        
        # 注意：这里不直接调用run_app(opts)，因为它会阻塞当前协程
        # 我们已经在entrypoint_function中实现了主要逻辑
        
        # 取消心跳任务
        heartbeat_task.cancel()
        
    except Exception as e:
        logger.exception(f"启动翻译服务失败: %s", e)
        raise
    finally:
        logger.info("⚙️ Worker exiting")

# ⚙️ Worker heartbeat task
async def worker_heartbeat():
    """Worker心跳任务"""
    global last_heartbeat
    
    while True:
        try:
            last_heartbeat = time.time()
            await asyncio.sleep(30)  # 每30秒更新一次心跳
        except asyncio.CancelledError:
            logger.info("⚙️ Heartbeat task cancelled")
            break
        except Exception as e:
            logger.error(f"⚙️ Heartbeat error: {e}")
            await asyncio.sleep(30)

async def entrypoint_function():
    """
    LiveKit Worker 入口点函数
    此函数包含主要应用逻辑
    """
    # 调用主函数
    await main()

async def main():
    """主要的音频翻译处理逻辑"""
    global is_translation_running, translation_sessions, last_heartbeat
    
    try:
        # 设置字幕处理器
        kr_subtitle_handler, vn_subtitle_handler = setup_subtitle_handlers()
        
        # 更新心跳
        last_heartbeat = time.time()
        
        # 创建三个不同的RealtimeModel
        logger.info("正在创建翻译模型...")
        
        # 1. 中文原音模型 - 仅用于广播原始语音
        zh_model = create_realtime_model(
            lang_code="zh",
            prompt="只需播放原始中文语音，无需翻译。",
            room_name=ROOM_ZH,
            livekit_url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            openai_api_key=OPENAI_API_KEY,
            text_callback=None  # 原音不需要文本回调
        )
        
        # 2. 中文到韩文翻译模型
        kr_model = create_realtime_model(
            lang_code="kr",
            prompt=KR_PROMPT,
            room_name=ROOM_KR,
            livekit_url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            openai_api_key=OPENAI_API_KEY,
            text_callback=kr_subtitle_handler
        )
        
        # 3. 中文到越南文翻译模型
        vn_model = create_realtime_model(
            lang_code="vn",
            prompt=VN_PROMPT,
            room_name=ROOM_VN,
            livekit_url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            openai_api_key=OPENAI_API_KEY,
            text_callback=vn_subtitle_handler
        )
        
        # 存储模型到全局变量
        translation_sessions = {
            "zh": zh_model,
            "kr": kr_model,
            "vn": vn_model
        }
        
        is_translation_running = True
        last_heartbeat = time.time()  # 再次更新心跳
        
        logger.info("所有翻译模型已创建...")
        logger.info(f"中文原音广播到房间: {ROOM_ZH}")
        logger.info(f"韩文翻译广播到房间: {ROOM_KR}")
        logger.info(f"越南文翻译广播到房间: {ROOM_VN}")
        logger.info("翻译服务正在后台运行...")
        
        # 注意：在这个新的架构中，我们不需要等待会话完成
        # 因为实际的Agent会话将由LiveKit Worker API自动管理
        
        # 保持服务运行
        while is_translation_running:
            await asyncio.sleep(1)
            last_heartbeat = time.time()
        
    except Exception as e:
        logger.exception(f"翻译服务启动失败: %s", e)
        is_translation_running = False
    finally:
        # 关闭所有会话
        await shutdown_translation_service()

async def shutdown_translation_service():
    """关闭翻译服务"""
    global is_translation_running, translation_sessions
    
    logger.info("⚙️ Worker shutdown")
    is_translation_running = False
    
    # 清理会话
    if translation_sessions:
        logger.info("正在清理翻译会话...")
        translation_sessions.clear()
    
    logger.info("翻译服务已关闭")

# ⚙️ Main execution
if __name__ == "__main__":
    # 获取端口号
    port = int(os.environ.get("PORT", 8000))
    
    # 启动FastAPI应用
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
