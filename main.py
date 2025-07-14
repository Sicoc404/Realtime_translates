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
from fastapi.middleware.cors import CORSMiddleware  # 添加CORS中间件
import uvicorn
from pydantic import BaseModel

from livekit.api import AccessToken, VideoGrants  # ⚙️ LiveKit token generation imports

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

# ⚙️ 全局变量存储服务状态
is_service_running = False
last_heartbeat = time.time()

# ⚙️ FastAPI lifespan setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ⚙️ Startup
    global is_service_running, last_heartbeat
    is_service_running = True
    last_heartbeat = time.time()
    logger.info("FastAPI Web服务启动中...")
    logger.info("🌐 Web服务已启动")
    logger.info("🤖 Agent服务已启动，可以处理翻译请求")
    
    # 启动字幕处理器
    on_kr, on_vn = setup_subtitle_handlers()
    
    # 启动翻译服务
    try:
        from session_factory import create_agent_session
        from deepgram_client import setup_deepgram_client
        
        # 创建Agent会话
        agent_session = create_agent_session()
        
        # 设置Deepgram客户端
        setup_deepgram_client(
            on_kr_translation=on_kr,
            on_vn_translation=on_vn,
            agent_session=agent_session
        )
        
        logger.info("✅ 翻译服务已成功启动")
    except Exception as e:
        logger.error(f"❌ 启动翻译服务失败: {str(e)}")
    
    # 启动心跳更新任务
    heartbeat_task = asyncio.create_task(update_heartbeat())
    
    yield  # 服务运行中...
    
    # ⚙️ Shutdown
    logger.info("⚙️ 正在关闭Web服务...")
    is_service_running = False
    heartbeat_task.cancel()
    logger.info("Web服务已关闭")

# ⚙️ Initialize FastAPI with lifespan
app = FastAPI(
    title="Real-time Translation Service", 
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
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
    global is_service_running, last_heartbeat
    
    current_time = time.time()
    heartbeat_age = current_time - last_heartbeat
    service_alive = heartbeat_age < 60  # 60秒内有心跳认为是活跃的
    
    return {
        "is_running": is_service_running,
        "service_alive": service_alive,
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

# ⚙️ Heartbeat update task
async def update_heartbeat():
    """更新心跳"""
    global last_heartbeat
    while is_service_running:
        last_heartbeat = time.time()
        await asyncio.sleep(30)  # 每30秒更新一次心跳

# ⚙️ Main execution
if __name__ == "__main__":
    # 获取端口号
    port = int(os.environ.get("PORT", 8000))
    
    # 启动翻译服务
    logger.info("🚀 启动Agent服务...")
    
    # 启动FastAPI应用
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
