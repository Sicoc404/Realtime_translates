import os
import json
import asyncio
import logging
from datetime import datetime
import warnings

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deepgram.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("deepgram_client")

# 全局变量存储DeepgramClient实例
deepgram_client = None

# 检查音频支持
HAS_AUDIO_SUPPORT = False
try:
    import numpy as np
    import websockets
    # 注意：sounddevice导入移到了类方法中
    HAS_AUDIO_SUPPORT = True
    logger.info("✅ 基本音频支持已启用 (numpy, websockets)")
except ImportError as e:
    logger.warning(f"⚠️ 音频支持已禁用: {str(e)}")
    logger.warning("⚠️ 将使用模拟模式，不会处理实际音频")

class DeepgramClient:
    """
    使用WebSocket连接Deepgram实时语音转写API的客户端
    
    将本地麦克风采集的音频实时发送到Deepgram进行转写，
    并通过回调函数将转写结果返回给调用方
    """
    
    # Deepgram API的WebSocket URL
    DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen"
    
    # 音频采样参数
    CHANNELS = 1  # 单声道
    SAMPLE_RATE = 16000  # 采样率16kHz
    DTYPE = 'int16'  # 16位整数
    CHUNK_SIZE = 4096  # 每个音频块的大小
    
    def __init__(
        self, 
        api_key: str, 
        on_transcript: callable,
        language: str = "zh-CN",
        model: str = "nova-2",
        interim_results: bool = True,
        punctuate: bool = True,
        endpointing: bool = True,
        device_index: int = None,
        simulation_mode: bool = False
    ):
        """
        初始化Deepgram客户端
        
        参数:
            api_key: Deepgram API密钥
            on_transcript: 转写结果回调函数，接收文本参数
            language: 音频语言，默认中文
            model: Deepgram模型，默认nova-2
            interim_results: 是否返回中间结果
            punctuate: 是否添加标点符号
            endpointing: 是否启用语音端点检测
            device_index: 输入设备索引，None表示默认设备
            simulation_mode: 是否使用模拟模式（无音频设备环境）
        """
        self.api_key = api_key
        self.on_transcript = on_transcript
        self.language = language
        self.model = model
        self.interim_results = interim_results
        self.punctuate = punctuate
        self.endpointing = endpointing
        self.device_index = device_index
        self.simulation_mode = simulation_mode or not HAS_AUDIO_SUPPORT
        
        self.ws = None
        self.audio_stream = None
        self.is_running = False
        self.last_transcript = ""
        
        # 检查API密钥
        if not self.api_key and not self.simulation_mode:
            logger.error("Deepgram API密钥未提供")
            raise ValueError("Deepgram API密钥未提供，请确保环境变量DEEPGRAM_API_KEY已设置")
        
        if self.simulation_mode:
            logger.warning("⚠️ Deepgram客户端运行在模拟模式，不会处理实际音频")
    
    async def _connect_websocket(self) -> None:
        """建立到Deepgram API的WebSocket连接"""
        if self.simulation_mode:
            logger.info("模拟模式：跳过WebSocket连接")
            return
            
        try:
            # 构建查询参数
            params = {
                "language": self.language,
                "model": self.model,
                "encoding": "linear16",
                "sample_rate": self.SAMPLE_RATE,
                "channels": self.CHANNELS,
                "interim_results": "true" if self.interim_results else "false",
                "punctuate": "true" if self.punctuate else "false",
            }
            
            if self.endpointing:
                params["endpointing"] = "true"
                
            # 构建URL查询字符串
            query = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{self.DEEPGRAM_URL}?{query}"
            
            # 连接WebSocket
            logger.info(f"正在连接Deepgram WebSocket: {url}")
            extra_headers = {"Authorization": f"Token {self.api_key}"}
            self.ws = await websockets.connect(url, extra_headers=extra_headers)
            logger.info("Deepgram WebSocket连接已建立")
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到Deepgram API: {str(e)}")
    
    async def _listen_for_results(self) -> None:
        """监听并处理Deepgram的响应"""
        if self.simulation_mode:
            logger.info("模拟模式：启动模拟转写")
            await self._run_simulation()
            return
            
        try:
            while self.is_running and self.ws and self.ws.open:
                try:
                    response = await self.ws.recv()
                    await self._process_response(response)
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket连接已关闭")
                    break
                except Exception as e:
                    logger.error(f"处理响应时出错: {str(e)}")
                    # 继续监听，不中断流程
        except Exception as e:
            logger.error(f"监听过程中发生错误: {str(e)}")
        finally:
            self.is_running = False
    
    async def _run_simulation(self) -> None:
        """在模拟模式下运行，生成模拟的转写结果"""
        sample_texts = [
            "你好，这是一个测试。",
            "欢迎使用实时翻译系统。",
            "这个系统可以将中文翻译成韩文和越南文。",
            "我们正在使用Groq进行翻译。",
            "希望这个系统能够帮助到你。"
        ]
        
        logger.info("🤖 模拟模式：开始生成模拟转写结果")
        
        try:
            while self.is_running:
                for text in sample_texts:
                    if not self.is_running:
                        break
                    
                    # 调用转写回调
                    self.on_transcript(text)
                    logger.info(f"📝 模拟转写: {text}")
                    
                    # 等待一段时间
                    await asyncio.sleep(10)  # 每10秒生成一条模拟转写
        except Exception as e:
            logger.error(f"模拟过程中发生错误: {str(e)}")
        finally:
            self.is_running = False
    
    async def _process_response(self, response: str) -> None:
        """处理Deepgram API的响应"""
        try:
            data = json.loads(response)
            
            # 检查是否为转写结果
            if "channel" in data and "alternatives" in data["channel"]:
                alt = data["channel"]["alternatives"][0]
                
                # 检查是否有转写文本
                if "transcript" in alt and alt["transcript"]:
                    transcript = alt["transcript"]
                    is_final = data.get("is_final", False)
                    
                    # 只在最终结果或文本变化时调用回调
                    if is_final or transcript != self.last_transcript:
                        self.last_transcript = transcript
                        try:
                            self.on_transcript(transcript)
                            if is_final:
                                logger.debug(f"最终转写结果: {transcript}")
                        except Exception as e:
                            logger.error(f"回调函数执行出错: {str(e)}")
            
            # 检查错误信息
            if "error" in data:
                logger.error(f"Deepgram API错误: {data['error']}")
                
        except json.JSONDecodeError:
            logger.error(f"无效的JSON响应: {response}")
        except Exception as e:
            logger.error(f"处理响应数据时出错: {str(e)}")
    
    async def _audio_callback(self, indata, frames, time, status) -> None:
        """
        音频采集回调函数，将采集到的音频发送到Deepgram
        
        此函数由sounddevice的InputStream调用
        """
        if self.simulation_mode:
            return
            
        if status:
            logger.warning(f"音频采集状态: {status}")
            
        if self.ws and self.ws.open and self.is_running:
            try:
                # 确保数据为16位整数
                audio_data = indata.copy()
                audio_data = (audio_data * 32767).astype(np.int16).tobytes()
                
                # 发送音频数据
                await self.ws.send(audio_data)
            except Exception as e:
                logger.error(f"发送音频数据时出错: {str(e)}")
    
    def _get_audio_devices(self) -> dict:
        """获取可用的音频输入设备"""
        if self.simulation_mode:
            return {"simulation": "模拟音频设备"}
            
        devices = {}
        try:
            # 导入sounddevice
            import sounddevice as sd
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices[i] = f"{device['name']} (输入通道: {device['max_input_channels']})"
        except ImportError:
            logger.warning("⚠️ sounddevice未安装，无法获取音频设备列表")
        except Exception as e:
            logger.error(f"获取音频设备列表失败: {str(e)}")
        
        return devices
    
    def list_audio_devices(self) -> None:
        """列出所有可用的音频输入设备"""
        if self.simulation_mode:
            logger.info("模拟模式：使用模拟音频设备")
            return
            
        devices = self._get_audio_devices()
        if devices:
            logger.info("可用的音频输入设备:")
            for idx, name in devices.items():
                logger.info(f"设备 #{idx}: {name}")
        else:
            logger.warning("未找到可用的音频输入设备")
    
    async def start_stream(self) -> None:
        """启动音频采集和实时转写"""
        if self.is_running:
            logger.warning("转写流已在运行")
            return
            
        self.is_running = True
        
        try:
            # 连接WebSocket（如果不是模拟模式）
            if not self.simulation_mode:
                await self._connect_websocket()
            
            # 启动结果监听任务
            listen_task = asyncio.create_task(self._listen_for_results())
            
            # 如果不是模拟模式，启动音频采集
            if not self.simulation_mode and HAS_AUDIO_SUPPORT:
                try:
                    # 导入sounddevice
                    import sounddevice as sd
                    # 设置音频输入回调
                    audio_callback = lambda indata, frames, time, status: asyncio.create_task(
                        self._audio_callback(indata, frames, time, status)
                    )
                    
                    logger.info("启动音频采集...")
                    self.audio_stream = sd.InputStream(
                        callback=audio_callback,
                        channels=self.CHANNELS,
                        samplerate=self.SAMPLE_RATE,
                        dtype=self.DTYPE,
                        blocksize=self.CHUNK_SIZE,
                        device=self.device_index
                    )
                    self.audio_stream.start()
                    
                    logger.info(f"Deepgram实时转写已启动，语言: {self.language}, 模型: {self.model}")
                except ImportError:
                    logger.warning("⚠️ sounddevice未安装，切换到模拟模式")
                    self.simulation_mode = True
            else:
                logger.info("模拟模式：跳过音频采集，使用模拟数据")
            
            # 等待结果监听任务完成
            await listen_task
            
        except Exception as e:
            logger.error(f"启动流程时发生错误: {str(e)}")
            self.is_running = False
            if self.ws and not self.simulation_mode:
                await self.ws.close()
            if self.audio_stream and not self.simulation_mode:
                self.audio_stream.stop()
                self.audio_stream.close()
                
            # 重新抛出异常以通知调用者
            raise
    
    async def stop_stream(self) -> None:
        """停止音频采集和实时转写"""
        if not self.is_running:
            logger.warning("转写流未在运行")
            return
            
        logger.info("正在停止Deepgram实时转写...")
        self.is_running = False
        
        # 如果不是模拟模式，关闭音频流和WebSocket
        if not self.simulation_mode:
            # 关闭音频流
            if self.audio_stream:
                try:
                    self.audio_stream.stop()
                    self.audio_stream.close()
                    self.audio_stream = None
                    logger.info("音频流已关闭")
                except Exception as e:
                    logger.error(f"关闭音频流时出错: {str(e)}")
            
            # 关闭WebSocket连接
            if self.ws:
                try:
                    await self.ws.close()
                    self.ws = None
                    logger.info("WebSocket连接已关闭")
                except Exception as e:
                    logger.error(f"关闭WebSocket时出错: {str(e)}")
        else:
            logger.info("模拟模式：停止模拟转写")
                
        logger.info("Deepgram实时转写已停止")


def setup_deepgram_client(on_kr_translation, on_vn_translation, agent_session):
    """
    设置Deepgram客户端，用于处理语音转写和翻译
    
    Args:
        on_kr_translation: 韩文翻译回调函数
        on_vn_translation: 越南文翻译回调函数
        agent_session: Agent会话对象，用于处理翻译
    """
    global deepgram_client
    
    logger.info("🔧 设置Deepgram客户端...")
    
    # 获取Deepgram API密钥
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        logger.warning("⚠️ 未设置DEEPGRAM_API_KEY环境变量，将使用模拟模式")
    
    # 检查是否强制使用模拟模式
    force_simulation = os.environ.get("FORCE_SIMULATION", "false").lower() == "true"
    
    # 确定是否使用模拟模式
    use_simulation = force_simulation or not HAS_AUDIO_SUPPORT or not api_key
    
    if use_simulation:
        logger.warning("⚠️ 使用模拟模式运行Deepgram客户端")
    
    # 定义转写回调函数
    def handle_transcript(text):
        """处理中文转写，并进行翻译"""
        logger.info(f"📝 中文转写: {text}")
        
        try:
            # 使用Groq LLM进行真正的翻译
            import asyncio
            
            async def translate_text():
                # 韩文翻译
                kr_translator = agent_session.get("kr_translator")
                if kr_translator:
                    try:
                        # 使用Groq LLM进行韩文翻译
                        kr_prompt = f"请将以下中文翻译成韩文，只返回翻译结果，不要任何解释：{text}"
                        kr_response = await kr_translator.achat(kr_prompt)
                        kr_translation = kr_response.content.strip()
                        
                        if kr_translation:
                            on_kr_translation(kr_translation)
                            logger.info(f"🇰🇷 韩文翻译: {kr_translation}")
                    except Exception as e:
                        logger.error(f"韩文翻译失败: {str(e)}")
                        on_kr_translation(f"[韩文翻译错误: {str(e)}]")
                
                # 越南文翻译
                vn_translator = agent_session.get("vn_translator")
                if vn_translator:
                    try:
                        # 使用Groq LLM进行越南文翻译
                        vn_prompt = f"请将以下中文翻译成越南文，只返回翻译结果，不要任何解释：{text}"
                        vn_response = await vn_translator.achat(vn_prompt)
                        vn_translation = vn_response.content.strip()
                        
                        if vn_translation:
                            on_vn_translation(vn_translation)
                            logger.info(f"🇻🇳 越南文翻译: {vn_translation}")
                    except Exception as e:
                        logger.error(f"越南文翻译失败: {str(e)}")
                        on_vn_translation(f"[越南文翻译错误: {str(e)}]")
            
            # 启动翻译任务
            asyncio.create_task(translate_text())
                
        except Exception as e:
            logger.error(f"❌ 翻译过程中出错: {str(e)}")
            # 提供错误回调
            on_kr_translation(f"[翻译错误: {str(e)}]")
            on_vn_translation(f"[翻译错误: {str(e)}]")
    
    # 创建Deepgram客户端
    try:
        # 根据环境自动判断是否使用模拟模式
        deepgram_client = DeepgramClient(
            api_key=api_key,
            on_transcript=handle_transcript,
            language="zh-CN",  # 中文
            model="nova-2",
            interim_results=True,
            punctuate=True,
            endpointing=True,
            simulation_mode=use_simulation  # 根据环境自动判断
        )
        
        # 启动异步任务来启动流
        asyncio.create_task(start_deepgram_client())
        
        logger.info("✅ Deepgram客户端设置成功")
        return deepgram_client
    
    except Exception as e:
        logger.error(f"❌ 设置Deepgram客户端失败: {str(e)}")
        raise e

async def start_deepgram_client():
    """启动Deepgram客户端"""
    global deepgram_client
    if deepgram_client:
        try:
            logger.info("🚀 启动Deepgram客户端...")
            await deepgram_client.start_stream()
        except Exception as e:
            logger.error(f"❌ 启动Deepgram客户端失败: {str(e)}")

# 简单的使用示例
async def example_usage():
    """示例：如何使用DeepgramClient"""
    # 定义转写结果回调
    def handle_transcript(text):
        print(f"实时转写: {text}")
    
    # 从环境变量获取API密钥
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("未找到DEEPGRAM_API_KEY环境变量")
        return
        
    # 创建客户端
    client = DeepgramClient(api_key=api_key, on_transcript=handle_transcript)
    
    try:
        # 启动转写流
        print("开始录音和转写，按Ctrl+C停止...")
        await client.start_stream()
    except KeyboardInterrupt:
        print("\n接收到停止信号")
    except Exception as e:
        print(f"错误: {str(e)}")
    finally:
        # 确保停止转写流
        await client.stop_stream()


# 如果直接运行此文件，执行示例
if __name__ == "__main__":
    asyncio.run(example_usage()) 
