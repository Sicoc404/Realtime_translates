import os
import json
import asyncio
import logging
import sounddevice as sd
import websockets
import numpy as np
from typing import Callable, Optional, Dict, Any
from datetime import datetime

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
        on_transcript: Callable[[str], None],
        language: str = "zh-CN",
        model: str = "nova-2",
        interim_results: bool = True,
        punctuate: bool = True,
        endpointing: bool = True,
        device_index: Optional[int] = None
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
        """
        self.api_key = api_key
        self.on_transcript = on_transcript
        self.language = language
        self.model = model
        self.interim_results = interim_results
        self.punctuate = punctuate
        self.endpointing = endpointing
        self.device_index = device_index
        
        self.ws = None
        self.audio_stream = None
        self.is_running = False
        self.last_transcript = ""
        
        # 检查API密钥
        if not self.api_key:
            logger.error("Deepgram API密钥未提供")
            raise ValueError("Deepgram API密钥未提供，请确保环境变量DEEPGRAM_API_KEY已设置")
    
    async def _connect_websocket(self) -> None:
        """建立到Deepgram API的WebSocket连接"""
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
            
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到Deepgram API: {str(e)}")
        except Exception as e:
            logger.error(f"连接时发生未知错误: {str(e)}")
            raise
    
    async def _listen_for_results(self) -> None:
        """监听并处理Deepgram的响应"""
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
        if status:
            logger.warning(f"音频采集状态: {status}")
            
        if self.ws and self.ws.open and self.is_running:
            try:
                # 确保数据为16位整数
                audio_data = indata.copy()
                audio_data = (audio_data * 32767).astype(np.int16).tobytes()
                
                # 发送音频数据
                await self.ws.send(audio_data)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("发送音频时WebSocket已关闭")
            except Exception as e:
                logger.error(f"发送音频数据时出错: {str(e)}")
    
    def _get_audio_devices(self) -> Dict[int, str]:
        """获取可用的音频输入设备"""
        devices = {}
        try:
            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices[i] = f"{device['name']} (输入通道: {device['max_input_channels']})"
        except Exception as e:
            logger.error(f"获取音频设备列表失败: {str(e)}")
        
        return devices
    
    def list_audio_devices(self) -> None:
        """列出所有可用的音频输入设备"""
        devices = self._get_audio_devices()
        if devices:
            logger.info("可用的音频输入设备:")
            for idx, name in devices.items():
                logger.info(f"设备 #{idx}: {name}")
        else:
            logger.warning("未找到可用的音频输入设备")
    
    async def start_stream(self) -> None:
        """启动音频采集和实时转写流程"""
        if self.is_running:
            logger.warning("转写流已在运行中")
            return
            
        try:
            # 显示可用设备信息
            self.list_audio_devices()
            
            # 连接WebSocket
            await self._connect_websocket()
            
            # 标记为运行状态
            self.is_running = True
            
            # 启动结果监听任务
            listen_task = asyncio.create_task(self._listen_for_results())
            
            # 设置音频输入回调
            audio_callback = lambda indata, frames, time, status: asyncio.create_task(
                self._audio_callback(indata, frames, time, status)
            )
            
            # 启动音频采集流
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
            
            # 等待结果监听任务完成
            await listen_task
            
        except Exception as e:
            logger.error(f"启动流程时发生错误: {str(e)}")
            self.is_running = False
            if self.ws:
                await self.ws.close()
            if self.audio_stream:
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
                
        logger.info("Deepgram实时转写已停止")


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