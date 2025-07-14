import asyncio
import os
import threading
import time  # 添加time模块
from contextlib import asynccontextmanager
from typing import Dict, Any
import pathlib
import logging  # 添加logging模块
import sys  # 添加sys模块

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # 添加CORS中间件
import uvicorn
from pydantic import BaseModel

from livekit.api import AccessToken, VideoGrants  # ⚙️ LiveKit token generation imports

# 设置FORCE_SIMULATION环境变量，强制使用模拟模式
os.environ["FORCE_SIMULATION"] = "true"

# 设置日志
logger = logging.getLogger("translation_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 打印Python版本和路径信息
logger.info(f"Python版本: {sys.version}")
logger.info(f"Python路径: {sys.path}")

# 加载环境变量
load_dotenv()
logger.info("环境变量已加载")

# 检查关键环境变量
groq_api_key = os.environ.get("GROQ_API_KEY", "")
if groq_api_key:
    logger.info("✅ GROQ_API_KEY已设置")
else:
    logger.warning("⚠️ GROQ_API_KEY未设置")

deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY", "")
if deepgram_api_key:
    logger.info("✅ DEEPGRAM_API_KEY已设置")
else:
    logger.warning("⚠️ DEEPGRAM_API_KEY未设置")

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
    try:
        logger.info("正在导入console_output模块...")
        from console_output import setup_subtitle_handlers, start_api
        logger.info("成功导入console_output模块")
        
        logger.info("正在设置字幕处理器...")
        on_kr, on_vn = setup_subtitle_handlers()
        logger.info("✅ 字幕处理器设置成功")
    except Exception as e:
        logger.error(f"❌ 设置字幕处理器失败: {str(e)}")
        on_kr = on_vn = lambda text: None  # 使用空函数作为回退
    
    # 启动翻译服务
    try:
        logger.info("正在导入session_factory模块...")
        from session_factory import create_agent_session
        logger.info("成功导入session_factory模块")
        
        logger.info("正在导入deepgram_client模块...")
        from deepgram_client import setup_deepgram_client
        logger.info("成功导入deepgram_client模块")
        
        # 创建Agent会话
        logger.info("正在创建Agent会话...")
        agent_session = create_agent_session()
        logger.info("✅ Agent会话创建成功")
        logger.info(f"Agent会话类型: {type(agent_session)}")
        
        # 设置Deepgram客户端
        logger.info("正在设置Deepgram客户端...")
        deepgram_client = setup_deepgram_client(
            on_kr_translation=on_kr,
            on_vn_translation=on_vn,
            agent_session=agent_session
        )
        
        logger.info("✅ 翻译服务已成功启动")
        logger.info(f"Deepgram客户端: {deepgram_client}")
    except ImportError as e:
        logger.error(f"❌ 导入模块失败: {str(e)}")
        logger.error(f"❌ 模块搜索路径: {sys.path}")
        logger.error("❌ 请检查LiveKit Agents是否正确安装")
        logger.error("❌ 尝试运行: pip install 'livekit-agents[groq]~=1.0'")
    except Exception as e:
        logger.error(f"❌ 启动翻译服务失败: {str(e)}")
        import traceback
        logger.error(f"❌ 错误详情: {traceback.format_exc()}")
    
    # 启动心跳更新任务
    try:
        logger.info("正在启动心跳更新任务...")
        heartbeat_task = asyncio.create_task(update_heartbeat())
        logger.info("✅ 心跳更新任务已启动")
        
        # 确保服务状态为运行中
        is_service_running = True
        logger.info("✅ 翻译服务状态已设置为运行中")
    except Exception as e:
        logger.error(f"❌ 启动心跳更新任务失败: {str(e)}")
        heartbeat_task = None
    
    yield  # 服务运行中...
    
    # ⚙️ Shutdown
    logger.info("⚙️ 正在关闭Web服务...")
    is_service_running = False
    if heartbeat_task:
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
        "worker_alive": service_alive,  # 修改字段名以匹配JavaScript代码
        "service_alive": service_alive,  # 保留原字段名以防其他地方使用
        "last_heartbeat": last_heartbeat,
        "heartbeat_age": heartbeat_age,
        "rooms": {
            "chinese": ROOM_ZH,
            "korean": ROOM_KR,
            "vietnamese": ROOM_VN
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
