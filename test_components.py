#!/usr/bin/env python3
"""
测试组件脚本 - 用于单独测试STT、LLM和TTS组件
"""

import asyncio
import os
import logging
import sys
from dotenv import load_dotenv

# 导入自定义调试组件
from livekit_agent import DebugDeepgramSTT, DebugGroqLLM, DebugCartesiaTTS
from translation_prompts import KR_PROMPT, VN_PROMPT, JP_PROMPT

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("component_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 检查环境变量
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY", "")

if not all([GROQ_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY]):
    logger.error("❌ 缺少必要的API密钥配置")
    sys.exit(1)


async def test_stt(audio_file_path="test_audio.wav"):
    """测试Deepgram STT组件"""
    logger.info(f"🎤 测试STT组件，使用音频文件: {audio_file_path}")
    
    try:
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()
            
        logger.info(f"📊 音频文件大小: {len(audio_bytes)} 字节")
        
        stt = DebugDeepgramSTT(
            model="nova-2", 
            language="zh",
            interim_results=True,
            endpointing=True,
            vad_events=True,
            punctuate=True
        )
        
        result = await stt.transcribe(audio_bytes)
        logger.info(f"✅ STT测试结果: {result}")
        return result
        
    except FileNotFoundError:
        logger.error(f"❌ 音频文件不存在: {audio_file_path}")
        return None
    except Exception as e:
        logger.error(f"❌ STT测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def test_llm(text="你好，今天天气真不错", target_lang="kr"):
    """测试Groq LLM组件"""
    logger.info(f"🧠 测试LLM组件，输入文本: {text}")
    
    try:
        llm = DebugGroqLLM(model="llama3-8b-8192")
        
        # 根据目标语言选择提示词
        if target_lang == "kr":
            prompt = f"{KR_PROMPT}\n\n{text}"
            logger.info("🇰🇷 使用韩文翻译提示词")
        elif target_lang == "vn":
            prompt = f"{VN_PROMPT}\n\n{text}"
            logger.info("🇻🇳 使用越南文翻译提示词")
        elif target_lang == "jp":
            prompt = f"{JP_PROMPT}\n\n{text}"
            logger.info("🇯🇵 使用日文翻译提示词")
        else:
            logger.error(f"❌ 不支持的目标语言: {target_lang}")
            return None
        
        logger.info(f"📤 发送给LLM的提示词: {prompt}")
        result = await llm.complete(prompt)
        logger.info(f"✅ LLM测试结果: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ LLM测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def test_tts(text="안녕하세요, 오늘 날씨가 정말 좋네요", language="ko"):
    """测试Cartesia TTS组件"""
    logger.info(f"🔊 测试TTS组件，输入文本: {text}, 语言: {language}")
    
    try:
        # 根据语言选择合适的声音ID
        voice_id = "a0e99841-438c-4a64-b679-ae501e7d6091"  # 默认声音ID
        
        tts = DebugCartesiaTTS(
            model="sonic-multilingual",
            voice=voice_id,
            language=language
        )
        
        audio_bytes = await tts.synthesize(text)
        output_file = f"test_tts_{language}.wav"
        
        with open(output_file, "wb") as f:
            f.write(audio_bytes)
            
        logger.info(f"✅ TTS测试结果已保存到 {output_file} (大小: {len(audio_bytes)} 字节)")
        return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ TTS测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def test_full_pipeline(audio_file_path="test_audio.wav", target_lang="kr"):
    """测试完整的STT-LLM-TTS管道"""
    logger.info(f"🔄 测试完整翻译管道: {audio_file_path} -> {target_lang}")
    
    # 1. STT: 音频 -> 文本
    stt_result = await test_stt(audio_file_path)
    if not stt_result:
        logger.error("❌ STT阶段失败，终止管道测试")
        return
    
    # 2. LLM: 中文文本 -> 目标语言文本
    llm_result = await test_llm(stt_result, target_lang)
    if not llm_result:
        logger.error("❌ LLM阶段失败，终止管道测试")
        return
    
    # 3. TTS: 目标语言文本 -> 目标语言音频
    language_code = {"kr": "ko", "vn": "vi", "jp": "ja"}.get(target_lang, "ko")
    tts_result = await test_tts(llm_result, language_code)
    if not tts_result:
        logger.error("❌ TTS阶段失败，终止管道测试")
        return
    
    logger.info("✅ 完整翻译管道测试成功!")
    logger.info(f"📝 中文识别结果: {stt_result}")
    logger.info(f"🌐 翻译结果: {llm_result}")
    logger.info(f"🔊 语音合成结果: test_tts_{language_code}.wav (大小: {len(tts_result)} 字节)")


async def test_record_audio(duration=5, output_file="test_audio.wav"):
    """录制测试音频"""
    try:
        import pyaudio
        import wave
        
        logger.info(f"🎤 开始录制 {duration} 秒的测试音频...")
        
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        frames = []
        
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)
            if i % 10 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        wf = wave.open(output_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        logger.info(f"\n✅ 录制完成，保存到 {output_file}")
        return output_file
        
    except ImportError:
        logger.error("❌ 请安装pyaudio: pip install pyaudio")
        return None
    except Exception as e:
        logger.error(f"❌ 录制音频失败: {str(e)}")
        return None


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法: python test_components.py [stt|llm|tts|pipeline|record]")
        print("  stt: 测试语音识别")
        print("  llm: 测试翻译")
        print("  tts: 测试语音合成")
        print("  pipeline: 测试完整管道")
        print("  record: 录制测试音频")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "stt":
        audio_file = sys.argv[2] if len(sys.argv) > 2 else "test_audio.wav"
        await test_stt(audio_file)
    elif command == "llm":
        text = sys.argv[2] if len(sys.argv) > 2 else "你好，今天天气真不错"
        lang = sys.argv[3] if len(sys.argv) > 3 else "kr"
        await test_llm(text, lang)
    elif command == "tts":
        text = sys.argv[2] if len(sys.argv) > 2 else "안녕하세요, 오늘 날씨가 정말 좋네요"
        lang = sys.argv[3] if len(sys.argv) > 3 else "ko"
        await test_tts(text, lang)
    elif command == "pipeline":
        audio_file = sys.argv[2] if len(sys.argv) > 2 else "test_audio.wav"
        lang = sys.argv[3] if len(sys.argv) > 3 else "kr"
        await test_full_pipeline(audio_file, lang)
    elif command == "record":
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        output_file = sys.argv[3] if len(sys.argv) > 3 else "test_audio.wav"
        await test_record_audio(duration, output_file)
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 