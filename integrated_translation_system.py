import os
import asyncio
import logging
from typing import Dict, Optional
from dotenv import load_dotenv

# 导入自定义模块
from deepgram_client import DeepgramClient
from cartesia import text_to_speech, tts_stream
from publisher import publish_audio, publish_audio_chunks, close_all_sessions

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("translation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("translation_system")

# 加载环境变量
load_dotenv()

# 翻译语言配置
LANGUAGES = {
    "ko": {
        "name": "韩文",
        "room": "room_kr"
    },
    "vi": {
        "name": "越南文",
        "room": "room_vn"
    }
}

class TranslationSystem:
    """
    实时语音翻译系统
    
    将中文语音实时转写并翻译成多种语言，播放翻译后的语音
    """
    
    def __init__(self):
        """初始化翻译系统"""
        self.deepgram_client = None
        self.is_running = False
        self.last_transcript = ""
        
        # 检查API密钥
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.cartesia_api_key = os.getenv("CARTESIA_API_KEY")
        
        if not self.deepgram_api_key:
            logger.error("缺少Deepgram API密钥，请设置DEEPGRAM_API_KEY环境变量")
        
        if not self.cartesia_api_key:
            logger.error("缺少Cartesia API密钥，请设置CARTESIA_API_KEY环境变量")
    
    async def handle_transcript(self, text: str):
        """
        处理Deepgram转写结果
        
        参数:
            text: 转写的中文文本
        """
        if text == self.last_transcript:
            return
            
        self.last_transcript = text
        logger.info(f"中文转写: {text}")
        
        # 为每种目标语言创建翻译任务
        tasks = []
        for lang_code, lang_info in LANGUAGES.items():
            task = asyncio.create_task(
                self.translate_and_speak(text, lang_code, lang_info["room"], lang_info["name"])
            )
            tasks.append(task)
        
        # 等待所有翻译任务完成
        await asyncio.gather(*tasks)
    
    async def translate_and_speak(self, text: str, lang_code: str, room_name: str, lang_name: str):
        """
        翻译文本并生成语音
        
        参数:
            text: 原始中文文本
            lang_code: 目标语言代码
            room_name: 目标房间名称
            lang_name: 语言名称（用于日志）
        """
        try:
            # 注意：实际项目中，这里可能需要调用翻译API
            # 这里我们直接使用Cartesia TTS进行模拟翻译+TTS的过程
            
            logger.info(f"正在生成{lang_name}语音: {text}")
            
            # 生成目标语言的音频
            audio_bytes = await text_to_speech(text, language=lang_code)
            
            # 发布音频到对应房间
            success = await publish_audio(audio_bytes, room_name)
            
            if success:
                logger.info(f"{lang_name}翻译已发布到房间 {room_name}")
            else:
                logger.error(f"{lang_name}翻译发布失败")
                
        except Exception as e:
            logger.error(f"{lang_name}翻译处理出错: {str(e)}")
    
    async def start(self):
        """启动翻译系统"""
        if self.is_running:
            logger.warning("翻译系统已经在运行")
            return
            
        if not self.deepgram_api_key or not self.cartesia_api_key:
            logger.error("无法启动翻译系统：缺少API密钥")
            return
        
        self.is_running = True
        
        try:
            # 创建Deepgram客户端
            logger.info("正在初始化Deepgram客户端...")
            self.deepgram_client = DeepgramClient(
                api_key=self.deepgram_api_key,
                on_transcript=self.handle_transcript,
                language="zh-CN"
            )
            
            # 启动Deepgram音频采集和转写
            logger.info("正在启动Deepgram语音转写...")
            await self.deepgram_client.start_stream()
            
            # 保持系统运行，直到被停止
            logger.info("翻译系统已启动，按Ctrl+C停止")
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("接收到停止信号")
            self.is_running = False
        except Exception as e:
            logger.error(f"翻译系统运行出错: {str(e)}")
            self.is_running = False
        finally:
            await self.stop()
    
    async def stop(self):
        """停止翻译系统"""
        logger.info("正在停止翻译系统...")
        
        # 停止Deepgram客户端
        if self.deepgram_client:
            await self.deepgram_client.stop_stream()
            self.deepgram_client = None
        
        # 关闭所有LiveKit会话
        await close_all_sessions()
        
        self.is_running = False
        logger.info("翻译系统已停止")

async def main():
    """主函数"""
    # 创建并启动翻译系统
    translation_system = TranslationSystem()
    
    try:
        await translation_system.start()
    except KeyboardInterrupt:
        logger.info("接收到停止信号")
    finally:
        await translation_system.stop()

if __name__ == "__main__":
    asyncio.run(main()) 