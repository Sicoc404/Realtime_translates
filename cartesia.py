import os
import logging
import aiohttp
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cartesia.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("cartesia_tts")

class CartesiaTTS:
    """
    Cartesia TTS API 客户端
    
    支持韩文和越南文文本转语音，提供同步和流式接口
    """
    
    # Cartesia API URL 配置
    HTTP_API_URL = "https://api.cartesia.io/v1/tts"
    WEBSOCKET_API_URL = "wss://api.cartesia.io/v1/tts/stream"
    
    # 语言代码映射
    LANGUAGE_CODES = {
        "ko": "ko-KR",  # 韩文
        "vi": "vi-VN"   # 越南文
    }
    
    # 默认配置
    DEFAULT_CONFIG = {
        "ko": {
            "voice": "ko-female-1",
            "sample_rate": 24000,
            "format": "wav"
        },
        "vi": {
            "voice": "vi-female-1",
            "sample_rate": 24000,
            "format": "wav"
        }
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Cartesia TTS 客户端
        
        参数:
            api_key: Cartesia API 密钥，默认从环境变量获取
        """
        self.api_key = api_key or os.getenv("CARTESIA_API_KEY")
        
        if not self.api_key:
            logger.warning("未提供 Cartesia API 密钥，请设置环境变量 CARTESIA_API_KEY")
    
    async def text_to_speech(self, text: str, language: str = "ko", 
                           voice: Optional[str] = None, 
                           format: str = "wav",
                           sample_rate: int = 24000) -> bytes:
        """
        将文本转换为语音 (HTTP 同步接口)
        
        参数:
            text: 要转换的文本
            language: 语言代码 ('ko'或'vi')
            voice: 指定的语音，默认根据语言选择
            format: 音频格式，默认'wav'
            sample_rate: 采样率，默认24000
            
        返回:
            bytes: 音频二进制数据
        """
        if not self.api_key:
            raise ValueError("Cartesia API 密钥未设置")
            
        # 验证语言代码
        if language not in self.LANGUAGE_CODES:
            raise ValueError(f"不支持的语言代码: {language}，支持的语言代码: {list(self.LANGUAGE_CODES.keys())}")
        
        # 使用默认配置
        config = self.DEFAULT_CONFIG.get(language, {}).copy()
        
        # 更新配置
        if voice:
            config["voice"] = voice
        if format:
            config["format"] = format
        if sample_rate:
            config["sample_rate"] = sample_rate
            
        # 准备请求数据
        payload = {
            "text": text,
            "language": self.LANGUAGE_CODES[language],
            **config
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/*"
        }
        
        try:
            logger.info(f"发送TTS请求: {language} 文本长度: {len(text)}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.HTTP_API_URL,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"TTS API错误: {response.status}, {error_text}")
                        raise Exception(f"TTS API错误: {response.status}, {error_text}")
                        
                    # 获取二进制音频数据
                    audio_data = await response.read()
                    logger.info(f"TTS成功: 接收到 {len(audio_data)} 字节的音频数据")
                    return audio_data
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP请求错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"TTS处理错误: {str(e)}")
            raise
    
    async def tts_stream(self, text: str, language: str = "ko",
                        voice: Optional[str] = None,
                        format: str = "wav", 
                        sample_rate: int = 24000) -> AsyncGenerator[bytes, None]:
        """
        将文本转换为流式语音 (WebSocket 流式接口)
        
        参数:
            text: 要转换的文本
            language: 语言代码 ('ko'或'vi')
            voice: 指定的语音，默认根据语言选择
            format: 音频格式，默认'wav'
            sample_rate: 采样率，默认24000
            
        返回:
            AsyncGenerator: 音频数据流，每个chunk为二进制数据
        """
        if not self.api_key:
            raise ValueError("Cartesia API 密钥未设置")
            
        # 验证语言代码
        if language not in self.LANGUAGE_CODES:
            raise ValueError(f"不支持的语言代码: {language}，支持的语言代码: {list(self.LANGUAGE_CODES.keys())}")
        
        # 使用默认配置
        config = self.DEFAULT_CONFIG.get(language, {}).copy()
        
        # 更新配置
        if voice:
            config["voice"] = voice
        if format:
            config["format"] = format
        if sample_rate:
            config["sample_rate"] = sample_rate
            
        # 准备请求数据
        payload = {
            "text": text,
            "language": self.LANGUAGE_CODES[language],
            **config
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        import json
        import websockets
        
        try:
            logger.info(f"开始WebSocket流式TTS: {language} 文本长度: {len(text)}")
            
            # 构建WebSocket URL (包含查询参数)
            query_params = "&".join([f"{k}={v}" for k, v in payload.items()])
            ws_url = f"{self.WEBSOCKET_API_URL}?{query_params}"
            
            async with websockets.connect(ws_url, extra_headers=headers) as websocket:
                # 发送初始化消息
                await websocket.send(json.dumps(payload))
                
                # 接收音频数据流
                chunk_count = 0
                while True:
                    try:
                        data = await websocket.recv()
                        
                        # 检查是否为控制消息
                        if isinstance(data, str):
                            msg = json.loads(data)
                            if msg.get("status") == "completed":
                                logger.info("流式TTS完成")
                                break
                            continue
                            
                        # 二进制数据则为音频块
                        chunk_count += 1
                        logger.debug(f"接收到音频数据块 #{chunk_count}: {len(data)} 字节")
                        yield data
                        
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("WebSocket连接已关闭")
                        break
                        
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"流式TTS处理错误: {str(e)}")
            raise

# 创建默认客户端实例
_default_client = None

def get_client() -> CartesiaTTS:
    """获取默认TTS客户端实例"""
    global _default_client
    if _default_client is None:
        _default_client = CartesiaTTS()
    return _default_client

async def text_to_speech(text: str, language: str = "ko") -> bytes:
    """
    将文本转换为语音
    
    这是一个便捷函数，使用默认客户端实例
    
    参数:
        text: 要转换的文本
        language: 语言代码 ('ko'或'vi')
        
    返回:
        bytes: 音频二进制数据
    """
    client = get_client()
    return await client.text_to_speech(text, language)

async def tts_stream(text: str, language: str = "ko") -> AsyncGenerator[bytes, None]:
    """
    将文本转换为流式语音
    
    这是一个便捷函数，使用默认客户端实例
    
    参数:
        text: 要转换的文本
        language: 语言代码 ('ko'或'vi')
        
    返回:
        AsyncGenerator: 音频数据流，每个chunk为二进制数据
    """
    client = get_client()
    async for chunk in client.tts_stream(text, language):
        yield chunk

# 示例用法
async def example_usage():
    """如何使用Cartesia TTS API的示例"""
    # 示例1: 同步API (一次性返回完整音频)
    try:
        # 韩语示例
        kr_audio = await text_to_speech("안녕하세요", language="ko")
        print(f"生成韩语音频: {len(kr_audio)} 字节")
        
        # 可以将音频传给publisher发布到LiveKit房间
        # await publisher.publish_audio(kr_audio, "room_kr")
        
        # 越南语示例
        vn_audio = await text_to_speech("Xin chào", language="vi")
        print(f"生成越南语音频: {len(vn_audio)} 字节")
        
        # await publisher.publish_audio(vn_audio, "room_vn")
        
    except Exception as e:
        print(f"同步TTS示例错误: {e}")
    
    # 示例2: 流式API (逐块返回音频)
    try:
        # 韩语流式示例
        audio_chunks = []
        async for chunk in tts_stream("안녕하세요, 오늘 기분이 어때요?", language="ko"):
            audio_chunks.append(chunk)
            # 实时处理可以:
            # await publisher.publish_audio_chunk(chunk, "room_kr")
        
        print(f"流式接收了 {len(audio_chunks)} 个音频块")
        
    except Exception as e:
        print(f"流式TTS示例错误: {e}")

if __name__ == "__main__":
    asyncio.run(example_usage()) 