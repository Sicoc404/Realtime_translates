from typing import Tuple, Callable
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
import threading

# 创建Rich控制台对象
console = Console()

# 线程锁，防止多线程并发写入
lock = threading.Lock()

def update_subtitles(kr_subtitle: str, vn_subtitle: str) -> Panel:
    """创建包含韩文和越南文字幕的面板"""
    kr_text = Text(f"韩文: {kr_subtitle}", style="bold cyan")
    vn_text = Text(f"越南文: {vn_subtitle}", style="bold yellow")
    
    return Panel(
        Text.assemble(kr_text, "\n", vn_text),
        title="实时翻译字幕",
        border_style="green"
    )

def setup_subtitle_handlers() -> Tuple[Callable[[str], None], Callable[[str], None]]:
    """
    设置字幕处理器
    
    返回:
        (韩文字幕处理器, 越南文字幕处理器)
    """
    # ⚙️ Added nonlocal vars for subtitle handling
    kr_subtitle = ""
    vn_subtitle = ""
    
    # 创建实时更新界面
    live = Live(update_subtitles(kr_subtitle, vn_subtitle), refresh_per_second=10)
    live.start()
    
    def on_kr(text: str) -> None:
        """处理韩文字幕"""
        # ⚙️ Added nonlocal vars for subtitle handling
        nonlocal kr_subtitle
        global kr_subtitle_global
        with lock:
            kr_subtitle = text
            kr_subtitle_global = text  # 同步更新全局变量用于API
            live.update(update_subtitles(kr_subtitle, vn_subtitle))
            print(f"[KR 字幕] {kr_subtitle}")
    
    def on_vn(text: str) -> None:
        """处理越南文字幕"""
        # ⚙️ Added nonlocal vars for subtitle handling
        nonlocal vn_subtitle
        global vn_subtitle_global
        with lock:
            vn_subtitle = text
            vn_subtitle_global = text  # 同步更新全局变量用于API
            live.update(update_subtitles(kr_subtitle, vn_subtitle))
            print(f"[VN 字幕] {vn_subtitle}")
    
    return on_kr, on_vn

# 全局字幕变量 - 供API使用
kr_subtitle_global = ""
vn_subtitle_global = ""

# 可选：添加FastAPI支持
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI(title="实时翻译字幕API")
    
    @app.get("/subtitles/kr")
    async def get_kr_subtitles():
        """获取韩文字幕"""
        return JSONResponse({"text": kr_subtitle_global, "lang": "kr"})
    
    @app.get("/subtitles/vn")
    async def get_vn_subtitles():
        """获取越南文字幕"""
        return JSONResponse({"text": vn_subtitle_global, "lang": "vn"})
    
    def start_api_server():
        """启动FastAPI服务器"""
        uvicorn.run(app, host="0.0.0.0", port=8000)
    
    # 在单独的线程中启动API服务器
    def start_api():
        api_thread = threading.Thread(target=start_api_server)
        api_thread.daemon = True
        api_thread.start()
        console.print("[bold green]字幕API服务已启动在 http://localhost:8000[/bold green]")
        
except ImportError:
    # 如果未安装FastAPI，则跳过API服务
    def start_api():
        console.print("[bold yellow]未安装FastAPI，仅使用控制台显示字幕[/bold yellow]") 
