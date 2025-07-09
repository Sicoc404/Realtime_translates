# 实时语音翻译系统

基于LiveKit和OpenAI实现的实时中文多语言翻译系统，支持将中文实时翻译成韩文和越南文，并提供语音播放和字幕显示功能。

## 功能特点

- **中文原音保留**：保留原始中文语音，用于参考
- **韩文实时翻译**：将中文翻译为韩文，同步播放语音和显示字幕
- **越南文实时翻译**：将中文翻译为越南文，同步播放语音和显示字幕
- **多房间广播**：不同语言翻译结果广播到不同的LiveKit房间
- **实时字幕显示**：在控制台或Web API中显示实时字幕

## 技术栈

- LiveKit Agents 框架
- OpenAI Realtime API
- Python 3.9+
- FastAPI (可选，用于Web字幕显示)

## 快速开始

### 环境准备

1. 克隆此仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置环境变量（在Render平台或本地.env文件中设置以下变量）：
   - `LIVEKIT_URL`：LiveKit服务器URL
   - `LIVEKIT_API_KEY`：LiveKit API密钥
   - `LIVEKIT_API_SECRET`：LiveKit API密钥
   - `OPENAI_API_KEY`：OpenAI API密钥

### 运行系统

```bash
python main.py
```

## 项目结构

- `main.py`: 主程序入口，创建并管理翻译会话
- `session_factory.py`: 翻译会话工厂，用于创建不同语言的翻译会话
- `translation_prompts.py`: 不同语言的翻译提示词
- `console_output.py`: 字幕显示和Web API功能
- `requirements.txt`: 项目依赖列表

## 访问字幕API

如果安装了FastAPI，可以通过以下URL访问实时字幕：

- 韩文字幕：`http://localhost:8000/subtitles/kr`
- 越南文字幕：`http://localhost:8000/subtitles/vn`

## 房间连接

- 中文原音：连接到 `room_zh` 房间
- 韩文翻译：连接到 `room_kr` 房间
- 越南文翻译：连接到 `room_vn` 房间

## 许可

MIT 