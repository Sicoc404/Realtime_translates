import os
import asyncio
from dotenv import load_dotenv
from deepgram_client import DeepgramClient
from livekit import agents
from livekit.agents.openai import register_openai_worker
from livekit.agents import AgentContext
from livekit.plugins.audio import AudioBroadcast
import openai.realtime

# 加载环境变量
load_dotenv()

# LiveKit 配置
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

# OpenAI API 密钥
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Deepgram API 密钥
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")

# 房间名称
ROOM_KR = "room_kr"  # 韩文翻译房间

# 韩文翻译提示词
KR_PROMPT = """
You are a real-time interpreter.
When the speaker speaks Chinese, translate verbally into Korean.
Maintain tone, pace, and emotion.
Respond only in Korean.
"""

class TranslationSession:
    def __init__(self):
        """初始化翻译会话"""
        self.transcription_buffer = ""  # 存储语音转写文本的缓冲区
        self.session = None  # LiveKit会话
        self.deepgram_client = None  # Deepgram客户端
    
    def handle_transcript(self, text):
        """处理从Deepgram接收的转写文本"""
        print(f"收到中文转写: {text}")
        # 更新缓冲区，保存转写文本用于翻译
        self.transcription_buffer = text
    
    async def setup_livekit_session(self):
        """设置LiveKit翻译会话"""
        # 注册OpenAI Worker
        register_openai_worker(api_key=OPENAI_API_KEY)
        
        # 创建会话上下文
        context = AgentContext(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            identity="kr_translator",
            name="Korean Translator"
        )
        
        # 创建会话
        self.session = agents.AgentSession(context)
        
        # 注册音频广播插件 - 广播翻译后的语音到房间
        audio_broadcast = AudioBroadcast(room_name=ROOM_KR)
        self.session.register_plugin(audio_broadcast)
        
        # 创建OpenAI实时模型，并将转写文本提供给它
        model = openai.realtime.RealtimeModel(
            model="gpt-4o-realtime-preview",  # 更新为最新模型名称
            audio_output=audio_broadcast,
            instructions=KR_PROMPT,  # ⚙️ Use instructions instead of system, per LiveKit doc
            voice="alloy",  # 设置语音模型
            temperature=0.8,  # 设置温度参数
            modalities=["text", "audio"],  # 指定模态
            turn_detection="server_vad",  # 使用服务器端语音活动检测
            text_callback=self.handle_kr_subtitle
        )
        
        # 这里我们不使用LiveKit音频输入，而是手动将转写文本发送给模型
        self.session.register_plugin(model)
        self.realtime_model = model
        
        # 启动会话
        await self.session.start()
        print("韩文翻译会话已启动")
        
        return self.session
    
    def handle_kr_subtitle(self, text):
        """处理韩文字幕回调"""
        print(f"韩文翻译: {text}")
    
    async def start_deepgram(self):
        """启动Deepgram语音转写"""
        # 创建Deepgram客户端
        self.deepgram_client = DeepgramClient(
            api_key=DEEPGRAM_API_KEY,
            on_transcript=self.handle_transcript,
            language="zh-CN"
        )
        
        # 启动转写流
        await self.deepgram_client.start_stream()
    
    async def process_transcription(self):
        """处理转写结果并发送给翻译模型"""
        last_sent = ""
        
        while True:
            # 如果有新的转写文本，发送给翻译模型
            if self.transcription_buffer and self.transcription_buffer != last_sent:
                text = self.transcription_buffer
                last_sent = text
                
                # 将中文转写文本发送给OpenAI模型进行翻译
                if self.realtime_model and text.strip():
                    print(f"发送中文文本到翻译模型: {text}")
                    self.realtime_model.add_text(text)
            
            # 等待一小段时间
            await asyncio.sleep(0.5)
    
    async def run(self):
        """运行整个翻译流程"""
        try:
            # 设置LiveKit会话
            await self.setup_livekit_session()
            
            # 启动Deepgram转写
            deepgram_task = asyncio.create_task(self.start_deepgram())
            
            # 启动转写处理循环
            process_task = asyncio.create_task(self.process_transcription())
            
            # 等待会话完成
            session_task = asyncio.create_task(self.session.wait_until_done())
            
            # 等待所有任务完成（或者其中一个失败）
            await asyncio.gather(deepgram_task, process_task, session_task)
            
        except KeyboardInterrupt:
            print("接收到停止信号")
        except Exception as e:
            print(f"运行过程中出错: {str(e)}")
        finally:
            # 清理资源
            await self.cleanup()
    
    async def cleanup(self):
        """清理所有资源"""
        print("正在清理资源...")
        
        # 停止Deepgram客户端
        if self.deepgram_client:
            await self.deepgram_client.stop_stream()
        
        # 关闭LiveKit会话
        if self.session:
            await self.session.close()
        
        print("所有资源已清理")


async def main():
    """主函数"""
    # 检查环境变量
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, OPENAI_API_KEY, DEEPGRAM_API_KEY]):
        print("错误: 请确保所有必要的环境变量都已设置")
        return
    
    # 创建并运行翻译会话
    translation = TranslationSession()
    print("正在启动中文 → 韩文翻译会话，使用Deepgram进行语音转写...")
    print("按Ctrl+C停止")
    
    try:
        await translation.run()
    except KeyboardInterrupt:
        print("\n接收到停止信号")


if __name__ == "__main__":
    asyncio.run(main()) 
