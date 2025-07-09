import os
import io
import asyncio
import logging
import wave
from typing import Optional, Dict, Any

from livekit import rtc
from livekit.plugins.audio import AudioBroadcast
from livekit.plugins.audio.broadcast import AudioSourceType

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("livekit_publisher")

class AudioPublisher:
    """LiveKit 音频发布器，将音频数据发布到指定房间"""
    
    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        """
        初始化 LiveKit 音频发布器
        
        参数:
            url: LiveKit 服务器地址，默认从环境变量获取
            api_key: LiveKit API 密钥，默认从环境变量获取
            api_secret: LiveKit API 密钥，默认从环境变量获取
        """
        self.url = url or os.getenv("LIVEKIT_URL")
        self.api_key = api_key or os.getenv("LIVEKIT_API_KEY")
        self.api_secret = api_secret or os.getenv("LIVEKIT_API_SECRET")
        
        if not all([self.url, self.api_key, self.api_secret]):
            logger.warning(f"LiveKit 配置不完整: URL={bool(self.url)}, API_KEY={bool(self.api_key)}, API_SECRET={bool(self.api_secret)}")
        
        # 存储活跃房间连接
        self.active_rooms: Dict[str, rtc.Room] = {}
        # 存储活跃的广播插件
        self.active_broadcasts: Dict[str, AudioBroadcast] = {}

    async def get_room(self, room_name: str) -> rtc.Room:
        """
        获取房间连接，如果不存在则创建新连接
        
        参数:
            room_name: LiveKit 房间名称
            
        返回:
            rtc.Room: LiveKit 房间连接
        """
        # 如果已有活跃连接，直接返回
        if room_name in self.active_rooms and self.active_rooms[room_name].connection_state == rtc.ConnectionState.CONNECTED:
            return self.active_rooms[room_name]

        # 创建新的房间连接
        room = rtc.Room()
        
        # 创建连接选项
        connect_options = rtc.RoomOptions(
            auto_subscribe=False,  # 不自动订阅其他参与者
            publish_only=True      # 仅发布，不接收
        )

        # 连接到房间
        identity = f"audio_publisher_{room_name}"
        try:
            logger.info(f"正在连接到房间 {room_name} 作为 {identity}")
            await room.connect(
                self.url,
                self.api_key,
                self.api_secret,
                identity,
                room_name,
                connect_options
            )
            logger.info(f"已连接到房间 {room_name}")
            
            # 存储并返回活跃连接
            self.active_rooms[room_name] = room
            return room
            
        except Exception as e:
            logger.error(f"连接到房间 {room_name} 失败: {str(e)}")
            raise

    async def get_broadcast(self, room_name: str) -> AudioBroadcast:
        """
        获取音频广播插件，如果不存在则创建
        
        参数:
            room_name: LiveKit 房间名称
            
        返回:
            AudioBroadcast: 音频广播插件实例
        """
        if room_name in self.active_broadcasts:
            return self.active_broadcasts[room_name]
            
        # 创建新的广播插件
        broadcast = AudioBroadcast(
            room_name=room_name,
            source_type=AudioSourceType.PCM_BUFFER
        )
        
        # 存储并返回广播插件
        self.active_broadcasts[room_name] = broadcast
        return broadcast

    async def publish_audio(self, audio_bytes: bytes, room_name: str) -> Dict[str, Any]:
        """
        将音频二进制发布到指定 LiveKit 房间中

        参数:
            audio_bytes: 音频二进制数据 (WAV 或 PCM 格式)
            room_name: 目标房间名称
            
        返回:
            Dict[str, Any]: 发布结果信息
        """
        result = {
            "success": False,
            "room": room_name,
            "error": None,
            "details": {}
        }
        
        try:
            # 获取音频参数信息
            audio_info = self._get_audio_info(audio_bytes)
            result["details"]["audio_info"] = audio_info
            
            # 获取或创建广播插件
            broadcast = await self.get_broadcast(room_name)
            
            # 发布音频数据
            logger.info(f"正在发布 {len(audio_bytes)} 字节的音频到房间 {room_name}")
            await broadcast.publish(audio_bytes)
            
            result["success"] = True
            logger.info(f"成功发布音频到房间 {room_name}")
            
        except Exception as e:
            error_msg = f"发布音频到房间 {room_name} 失败: {str(e)}"
            logger.error(error_msg)
            result["error"] = error_msg
            
        return result

    def _get_audio_info(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        尝试获取音频信息
        
        参数:
            audio_bytes: 音频二进制数据
            
        返回:
            Dict[str, Any]: 音频信息
        """
        info = {
            "size_bytes": len(audio_bytes),
            "format": "unknown"
        }
        
        # 尝试识别为WAV格式
        try:
            with io.BytesIO(audio_bytes) as buffer:
                with wave.open(buffer, 'rb') as wav:
                    info.update({
                        "format": "wav",
                        "channels": wav.getnchannels(),
                        "sample_rate": wav.getframerate(),
                        "sample_width": wav.getsampwidth(),
                        "duration_seconds": wav.getnframes() / wav.getframerate()
                    })
            return info
        except Exception:
            # 不是WAV格式，假设为PCM
            info["format"] = "pcm"
            return info

    async def close_room(self, room_name: str) -> bool:
        """
        关闭到指定房间的连接
        
        参数:
            room_name: LiveKit 房间名称
            
        返回:
            bool: 是否成功关闭
        """
        if room_name in self.active_rooms:
            try:
                logger.info(f"正在关闭房间 {room_name} 的连接")
                await self.active_rooms[room_name].disconnect()
                del self.active_rooms[room_name]
                
                # 清理广播插件
                if room_name in self.active_broadcasts:
                    del self.active_broadcasts[room_name]
                    
                logger.info(f"已关闭房间 {room_name} 的连接")
                return True
            except Exception as e:
                logger.error(f"关闭房间 {room_name} 连接失败: {str(e)}")
                return False
        return True  # 房间未连接也视为关闭成功

    async def close_all(self) -> None:
        """关闭所有活跃的房间连接"""
        for room_name in list(self.active_rooms.keys()):
            await self.close_room(room_name)

# 全局单例
_default_publisher = None

def get_publisher() -> AudioPublisher:
    """获取默认音频发布器实例"""
    global _default_publisher
    if _default_publisher is None:
        _default_publisher = AudioPublisher()
    return _default_publisher

async def publish_audio(audio_bytes: bytes, room_name: str) -> Dict[str, Any]:
    """
    将音频二进制发布到指定 LiveKit 房间中

    这是一个便捷函数，使用默认发布器实例

    参数:
        audio_bytes: 音频二进制数据 (WAV 或 PCM 格式)
        room_name: 目标房间名称
        
    返回:
        Dict[str, Any]: 发布结果信息
    """
    publisher = get_publisher()
    return await publisher.publish_audio(audio_bytes, room_name)

async def close_all_rooms() -> None:
    """关闭所有活跃的房间连接"""
    publisher = get_publisher()
    await publisher.close_all()

# 示例用法
async def example():
    # 假设从Cartesia获取了音频数据
    # from cartesia import text_to_speech
    # audio_bytes = await text_to_speech("안녕하세요", language="ko")
    
    # 读取示例WAV文件作为演示
    try:
        with open("example.wav", "rb") as f:
            audio_bytes = f.read()
            
        # 发布到指定房间
        result = await publish_audio(audio_bytes, room_name="room_kr")
        print(f"发布结果: {result}")
    except FileNotFoundError:
        print("示例文件不存在，请先创建example.wav文件")
    finally:
        # 关闭所有连接
        await close_all_rooms()

if __name__ == "__main__":
    asyncio.run(example()) 