#!/usr/bin/env python3
"""
仅Web服务版本 - 用于Render部署
Agent服务需要单独部署或本地运行
"""

import os
import time
import pathlib
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel

from livekit.api import AccessToken, VideoGrants

# 设置日志
logger = logging.getLogger("web_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 加载环境变量
load_dotenv()

# LiveKit 配置
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "wss://your-livekit-server.com")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")

# 房间名称
ROOM_ZH = "room_zh"  # 中文原音房间
ROOM_KR = "room_kr"  # 韩文翻译房间
ROOM_VN = "room_vn"  # 越南文翻译房间

# 全局变量存储服务状态
is_service_running = False
last_heartbeat = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    global is_service_running, last_heartbeat
    is_service_running = True
    last_heartbeat = time.time()
    logger.info("🌐 Web服务已启动")
    logger.info("⚠️  注意：Agent服务需要单独部署才能进行翻译")
    
    yield  # 服务运行中...
    
    # 关闭
    logger.info("⚙️ 正在关闭Web服务...")
    is_service_running = False
    logger.info("Web服务已关闭")

# 初始化FastAPI
app = FastAPI(
    title="Real-time Translation Web Service", 
    version="1.0.0",
    lifespan=lifespan
)

# 挂载静态文件
static_dir = pathlib.Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def homepage():
    """根路由，返回index.html页面"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
        <head><title>Real-time Translation Service</title></head>
        <body>
            <h1>Real-time Translation Service</h1>
            <p>Web service is running!</p>
            <p>⚠️ Agent service needs to be deployed separately for translation to work.</p>
        </body>
        </html>
        """

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/status")
async def get_status():
    """获取服务状态"""
    global is_service_running, last_heartbeat
    
    current_time = time.time()
    heartbeat_age = current_time - last_heartbeat
    service_alive = heartbeat_age < 60
    
    return {
        "web_service_running": is_service_running,
        "service_alive": service_alive,
        "last_heartbeat": last_heartbeat,
        "heartbeat_age": heartbeat_age,
        "rooms": {
            "zh": ROOM_ZH,
            "kr": ROOM_KR,
            "vn": ROOM_VN
        },
        "agent_service_note": "Agent service needs to be deployed separately",
        "timestamp": current_time
    }

class TokenRequest(BaseModel):
    roomName: str
    identity: str

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

# 主执行
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"🚀 启动Web服务在端口 {port}")
    logger.info("📋 支持的功能:")
    logger.info("  ✅ Web界面")
    logger.info("  ✅ LiveKit Token生成")
    logger.info("  ✅ 房间连接")
    logger.info("  ⚠️  翻译功能需要Agent服务")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    ) 