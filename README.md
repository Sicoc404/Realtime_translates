# 实时翻译服务 - Groq集成版本

本项目已从OpenAI切换到Groq，使用LiveKit官方文档推荐的STT-LLM-TTS管道架构。

## 🔧 技术栈

- **STT (语音转文本)**: Deepgram Nova-2 模型
- **LLM (大语言模型)**: Groq Llama3-8B-8192 模型  
- **TTS (文本转语音)**: Cartesia Sonic-Multilingual 模型
- **实时通信**: LiveKit WebRTC
- **Web服务**: FastAPI

## 📋 环境变量配置

在`.env`文件中配置以下环境变量：

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# AI Provider API Keys
GROQ_API_KEY=your-groq-api-key
DEEPGRAM_API_KEY=your-deepgram-api-key
CARTESIA_API_KEY=your-cartesia-api-key

# Optional: Server Port
PORT=8000
```

## 🚀 安装和运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量（在Render平台或`.env`文件中配置）

3. **方法一：一键启动所有服务**
```bash
python start_services.py
```

4. **方法二：分别启动服务**
```bash
# 终端1：启动Web服务
python main.py

# 终端2：启动Agent服务
python agent_runner.py dev
```

## 🏠 房间配置

系统支持三个房间：

- **room_zh**: 中文原音房间（不翻译）
- **room_kr**: 韩文翻译房间（中文→韩文）
- **room_vn**: 越南文翻译房间（中文→越南文）

## 📡 API端点

- `GET /`: 主页面
- `GET /health`: 健康检查
- `GET /status`: 服务状态
- `POST /token`: 生成LiveKit访问令牌

## 🔄 正确的使用流程

### 🎤 讲师端（AI Speaker）
1. 打开网页，点击右上角的 **🎤 AI Speaker** 按钮
2. 授权麦克风权限
3. 开始讲话，系统会自动：
   - 将中文语音同时发送到所有房间（room_zh, room_kr, room_vn）
   - 各房间的Agent接收音频并进行相应处理

### 👂 听众端
1. 选择语言房间：
   - **中文原音房间**: 听到讲师的原始中文语音
   - **韩文翻译房间**: 听到AI翻译的韩文语音 + 韩文字幕
   - **越南文翻译房间**: 听到AI翻译的越南文语音 + 越南文字幕

### 🔄 技术处理流程
1. **音频输入**: 讲师通过AI Speaker按钮开始广播
2. **多房间分发**: 同一音频流同时发送到3个房间
3. **分别处理**: 
   - room_zh: 直接播放原音
   - room_kr: Deepgram STT → Groq LLM翻译 → Cartesia TTS韩文
   - room_vn: Deepgram STT → Groq LLM翻译 → Cartesia TTS越南文
4. **实时传输**: LiveKit WebRTC进行实时音频传输

## 📝 主要变更

从OpenAI切换到Groq的主要变更：

1. **依赖更新**: 
   - 移除 `openai` 依赖
   - 添加 `groq` 和相关插件依赖

2. **架构变更**:
   - 从OpenAI RealtimeModel切换到STT-LLM-TTS管道
   - 使用AgentSession管理会话

3. **配置变更**:
   - `OPENAI_API_KEY` → `GROQ_API_KEY`
   - 新增 `DEEPGRAM_API_KEY` 和 `CARTESIA_API_KEY`

4. **代码结构**:
   - `session_factory.py`: 使用Groq LLM替代OpenAI RealtimeModel
   - `main.py`: 更新为FastAPI + Agent架构
   - `agent_runner.py`: 新增独立的Agent运行器

## 🎯 性能优势

使用Groq的优势：

- **更快的推理速度**: Groq专为LLM推理优化
- **更低的延迟**: 适合实时应用
- **成本效益**: 相比OpenAI更经济
- **开源模型**: 使用Llama3等开源模型

## 🔧 故障排除

1. **API密钥错误**: 确保所有API密钥正确配置
2. **模型不可用**: 检查Groq模型名称是否正确
3. **网络连接**: 确保LiveKit服务器可访问
4. **依赖问题**: 重新安装requirements.txt中的依赖

## 📚 参考文档

- [LiveKit Groq集成文档](https://docs.livekit.io/agents/integrations/groq/)
- [Groq API文档](https://console.groq.com/docs)
- [LiveKit Agent文档](https://docs.livekit.io/agents/) 
