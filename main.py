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
# ⚙️ Use Groq LLM from livekit.plugins.groq per docs
from livekit.plugins import groq, deepgram, cartesia
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

# Groq API 密钥
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# 房间名称
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间
ROOM_VN = "room_vn"  # 越南文翻译房间

# ⚙️ 全局变量存储会话状态
translation_sessions = {}
is_translation_running = False
worker_task = None
last_heartbeat = time.time()

# ⚙️ 创建翻译Agent类
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
        # 启动心跳任务
        heartbeat_task = asyncio.create_task(worker_heartbeat())
        
        # 启动主服务
        await main()
        
        # 取消心跳任务
        heartbeat_task.cancel()
        
    except Exception as e:
        logger.exception(f"启动翻译服务失败: %s", e)
        raise
    finally:
        logger.info("⚙️ Worker exiting")

async def entrypoint_function(ctx: agents.JobContext):
    """
    LiveKit Worker 入口点函数 - 按照官方文档实现
    此函数处理Agent会话
    """
    global is_translation_running, last_heartbeat
    
    try:
        # 更新心跳
        last_heartbeat = time.time()
        
        # 获取房间名称来确定翻译语言
        room_name = ctx.room.name
        logger.info(f"🏠 Agent joining room: {room_name}")
        
        # 根据房间名称确定翻译类型
        if room_name == ROOM_ZH:
            # 中文原音房间 - 不需要翻译
            agent = TranslationAgent("zh", "你是一个中文语音助手，直接播放原始中文语音。")
            instructions = "播放原始中文语音，无需翻译。"
        elif room_name == ROOM_KR:
            # 韩文翻译房间
            agent = TranslationAgent("kr", KR_PROMPT)
            instructions = KR_PROMPT
        elif room_name == ROOM_VN:
            # 越南文翻译房间
            agent = TranslationAgent("vn", VN_PROMPT)
            instructions = VN_PROMPT
        else:
            # 默认中文房间
            agent = TranslationAgent("zh", "你是一个中文语音助手。")
            instructions = "你是一个中文语音助手。"
        
        # 创建AgentSession
        session = AgentSession(
            stt=deepgram.STT(
                model="nova-2",
                language="zh"  # 中文语音识别
            ),
            llm=groq.LLM(
                model="llama3-8b-8192",
                api_key=GROQ_API_KEY
            ),
            tts=cartesia.TTS(
                model="sonic-multilingual",
                voice="a0e99841-438c-4a64-b679-ae501e7d6091"  # 多语言语音合成
            ),
        )
        
        # 启动会话
        await session.start(
            room=ctx.room,
            agent=agent
        )
        
        # 连接到房间
        await ctx.connect()
        
        # 生成初始回复
        await session.generate_reply(
            instructions=instructions
        )
        
        is_translation_running = True
        logger.info(f"✅ Agent started for room {room_name}")
        
        # 保持会话运行
        while is_translation_running:
            await asyncio.sleep(1)
            last_heartbeat = time.time()
            
    except Exception as e:
        logger.exception(f"Agent session failed: %s", e)
        is_translation_running = False
    finally:
        logger.info(f"🔚 Agent session ended for room {ctx.room.name}")

async def main():
    """主要的音频翻译处理逻辑 - 使用Groq LLM和AgentSession"""
    global is_translation_running, translation_sessions, last_heartbeat
    
    try:
        # 设置字幕处理器
        kr_subtitle_handler, vn_subtitle_handler = setup_subtitle_handlers()
        
        # 更新心跳
        last_heartbeat = time.time()
        
        logger.info("正在创建Groq LLM翻译模型...")
        
        # 验证Groq API密钥
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        logger.info("✅ Groq API Key configured")
        logger.info("🚀 Translation service ready to handle agent sessions")
        
        is_translation_running = True
        last_heartbeat = time.time()
        
        logger.info("翻译服务已启动，等待Agent会话...")
        logger.info(f"中文原音房间: {ROOM_ZH}")
        logger.info(f"韩文翻译房间: {ROOM_KR}")
        logger.info(f"越南文翻译房间: {ROOM_VN}")
        
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
