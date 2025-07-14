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

# 注释掉强制模拟模式，让系统根据环境自动判断
# os.environ["FORCE_SIMULATION"] = "true"

# 设置日志
logger = logging.getLogger("translation_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("translation_service.log"),
        logging.StreamHandler()
    ]
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

# 房间名称 - 简化版本，与前端保持一致
ROOM_ZH = "zh"    # 中文原音房间
ROOM_KR = "kr"    # 韩文翻译房间  
ROOM_VN = "vn"    # 越南文翻译房间

# 注释掉旧的导入，现在只使用LiveKit Agent系统
# 旧系统：
# from deepgram_client import setup_deepgram_client, start_deepgram_client
# from integrated_translation_system import TranslationSystem

# ✅ 新系统：只使用LiveKit Agent
# Agent系统会自动处理STT-LLM-TTS管道，无需手动管理Deepgram连接

# ⚙️ 全局变量存储服务状态
is_service_running = False
last_heartbeat = time.time()
agent_processes = {}  # 存储Agent进程

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
    
    # 启动LiveKit Agent服务
    try:
        logger.info("正在启动LiveKit Agent服务...")
        
        # 检查必要的环境变量
        required_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            logger.warning(f"⚠️ 缺少LiveKit环境变量: {', '.join(missing_vars)}")
            logger.warning("⚠️ Agent服务将无法启动")
        else:
            # 启动Agent服务进程
            await start_agent_services()
            logger.info("✅ LiveKit Agent服务已启动")
        
        logger.info("✅ 翻译服务已成功启动")
        
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
    
    # 停止Agent服务
    await stop_agent_services()
    
    if heartbeat_task:
        heartbeat_task.cancel()
    logger.info("Web服务已关闭")

async def start_agent_services():
    """启动LiveKit Agent服务"""
    global agent_processes
    
    try:
        # 导入LiveKit agents
        from livekit import agents
        from livekit.agents import WorkerOptions, Worker
        
        # 导入我们的Agent入口点
        from livekit_agent import entrypoint
        
        logger.info("🚀 启动LiveKit Agent服务...")
        
        # 创建工作器选项
        worker_options = WorkerOptions(
            entrypoint_fnc=entrypoint,
            # 设置Agent名称以启用显式调度
            agent_name="translation-agent",
            # 开发模式设置
            load_threshold=float('inf'),  # 开发模式下不限制负载
        )
        
        # 创建Worker实例
        worker = Worker(worker_options)
        
        # 启动工作器任务
        worker_task = asyncio.create_task(worker.run())
        
        agent_processes["translation_worker"] = {
            "task": worker_task,
            "worker": worker
        }
        
        logger.info("✅ LiveKit Agent工作器已启动")
        logger.info("🎧 Agent正在等待房间连接...")
        
    except ImportError as e:
        logger.error(f"❌ 导入LiveKit Agent失败: {str(e)}")
        logger.warning("⚠️ 请确保安装了livekit-agents包")
    except Exception as e:
        logger.error(f"❌ 启动Agent服务失败: {str(e)}")

async def stop_agent_services():
    """停止LiveKit Agent服务"""
    global agent_processes
    
    logger.info("🛑 停止Agent服务...")
    
    for name, process_info in agent_processes.items():
        try:
            if isinstance(process_info, dict) and "worker" in process_info:
                worker = process_info["worker"]
                task = process_info["task"]
                
                logger.info(f"🔄 关闭Agent工作器: {name}")
                await worker.aclose()
                
                if not task.cancelled():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
                logger.info(f"✅ Agent工作器已停止: {name}")
            else:
                # 向后兼容：处理旧的任务格式
                if hasattr(process_info, 'cancel'):
                    process_info.cancel()
                    try:
                        await process_info
                    except asyncio.CancelledError:
                        pass
        except Exception as e:
            logger.error(f"❌ 停止Agent工作器失败 {name}: {str(e)}")
    
    agent_processes.clear()
    logger.info("🏁 所有Agent服务已停止")

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
    """提供主页面"""
    index_file = pathlib.Path(__file__).parent / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding='utf-8'))
    else:
        return HTMLResponse(content="<h1>实时翻译服务</h1><p>index.html 文件未找到</p>")

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

@app.post("/token")
async def create_token(request: TokenRequest):
    """生成LiveKit访问令牌"""
    try:
        # 创建访问令牌
        from livekit.api import AccessToken, VideoGrants
        
        # 创建VideoGrants
        video_grant = VideoGrants(
            room=request.roomName,
            room_join=True,
            can_publish=True,
            can_subscribe=True
        )
        
        # 创建AccessToken
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(request.identity)
        token.with_grants(video_grant)
        
        # 生成JWT令牌
        jwt_token = token.to_jwt()
        
        return {
            "token": jwt_token,
            "url": LIVEKIT_URL,
            "room": request.roomName,
            "identity": request.identity
        }
    except Exception as e:
        logger.error(f"生成令牌失败: {str(e)}")
        return {"error": f"生成令牌失败: {str(e)}"}

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
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
