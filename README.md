# AI 小伙伴 - 儿童智能陪伴系统 
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/alexzhu0/AI_toy/pulls)

这是一个专门为儿童设计的AI陪伴系统，由一个叫"念念"的AI伙伴陪伴孩子成长。目前主要服务对象是一个叫"帅帅"的5岁小朋友。

<details>
<summary><b>🌟 特色功能</b></summary>

### 1. 温暖的语音对话
- 用温柔的声音和孩子交谈
- 能听懂孩子说的话并给出回应
- 会耐心倾听，不打断孩子说话
- 适合场景：
  * 孩子想找人说话的时候
  * 父母暂时没空陪伴时
  * 孩子需要倾诉的时候

### 2. 情感理解与支持
- 能察觉孩子是否开心、难过、生气或害怕
- 根据孩子的情绪给出安慰和鼓励
- 引导孩子学会表达感受
- 适合场景：
  * 孩子心情不好时
  * 遇到困难需要鼓励时
  * 想分享快乐的时候

### 3. 社交能力培养
- 帮助害羞的孩子建立自信
- 教会孩子如何交朋友
- 鼓励表达自己的想法
- 适合场景：
  * 孩子不知道如何交朋友时
  * 想练习社交对话时
  * 需要建立自信时

### 4. 智能记忆系统
- 记住与孩子的对话内容
- 记住孩子喜欢什么、不喜欢什么
- 能够延续之前的话题
- 适合场景：
  * 想继续之前的话题时
  * 回忆共同的经历时
  * 分享新鲜事物时
</details>

<details>
<summary><b>💡 应用场景举例</b></summary>

### 日常陪伴
- 早晨问候："帅帅，早上好！今天想和我说说话吗？"
- 情绪安抚："看你今天不太开心，想和念念说说发生了什么吗？"
- 分享快乐："真棒！和我说说今天最开心的事情吧！"

### 社交辅导
- 交友指导："帅帅，要不要和我练习一下怎么和新朋友打招呼？"
- 自信培养："你做得很棒！要相信自己，慢慢来没关系的。"
- 情绪表达："能告诉我为什么觉得害怕吗？我们一起想办法。"

### 学习成长
- 兴趣培养："你喜欢画画啊？给我讲讲你画的是什么吧！"
- 知识探索："想知道为什么天空是蓝色的吗？让我给你解释一下。"
- 生活技能："我们一起学习整理房间好不好？"
</details>

## 🎯 核心优势

1. **安全可靠**
   - 所有对话本地存储，保护隐私
   - 内容过滤，确保对话健康积极
   - 家长可随时查看对话记录

2. **个性化互动**
   - 根据孩子性格调整对话方式
   - 记住孩子的喜好和习惯
   - 针对性地培养和引导

3. **持续学习**
   - 通过对话了解孩子的变化
   - 不断优化互动策略
   - 成长记录可供回顾

4. **高可靠性设计**
   - 完善的错误处理机制
   - 自动重连和网络故障恢复
   - 数据库连接池和事务管理

## 🚀 快速开始

### 环境要求
- Python 3.8+
- FFmpeg (音频处理)
- 有效的SSL证书
- 麦克风和扬声器设备

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/alexzhu0/AI_toy.git
cd AI_toy
```

2. **配置环境**
```bash
# 使用pip
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 或使用conda
conda create -n AItoy python=3.8
conda activate AItoy

# 安装依赖
pip install -r requirements.txt
```

3. **设置环境变量**
```bash
# 在项目根目录创建 .env 文件
echo "DEEPSEEK_API_KEY=your_api_key_here" > .env
```

4. **生成SSL证书**
```bash
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes
```

5. **运行配置检查工具**
```bash
python check_config.py
```

6. **启动服务**
```bash
# 启动服务器
python main.py

# 或使用命令行客户端
python cli.py
```

## 🔧 技术架构

<details>
<summary><b>系统架构</b></summary>

```
AI_toy系统架构
├── 前端层
│   ├── 语音输入/输出
│   ├── WebSocket通信
│   └── 用户界面
├── 服务层
│   ├── FastAPI服务器
│   ├── 讯飞语音服务
│   └── Edge TTS服务
├── 核心层
│   ├── 对话管理(LangChain)
│   ├── AI对话(DeepSeek)
│   └── 状态管理
└── 数据层
    ├── SQLite数据库
    ├── 配置文件
    └── SSL证书
```
</details>

<details>
<summary><b>核心组件</b></summary>

1. **语音处理**
   - **讯飞语音识别**：
     * WebSocket实时语音识别
     * 支持中文语音精准识别
     * 自动语音端点检测
     * 动态修正和噪音抑制
   - **Edge TTS语音合成**：
     * 使用zh-CN-XiaoxiaoNeural音色
     * 自然流畅的中文语音输出
     * 可配置的语音参数
   - **WebSocket实时通信**：
     * 全双工音频数据传输
     * 心跳检测机制
     * 自动重连和错误恢复

2. **对话系统**
   - **DeepSeek对话引擎**：
     * 基于大规模语言模型
     * 定制化儿童对话场景
     * 温和友好的对话风格
   - **LangChain对话管理**：
     * 基于ConversationBufferMemory的对话历史管理
     * AgentExecutor工具函数调用链
     * 自定义工具函数集成
     * 动态提示词模板

3. **记忆系统**
   - **本地数据库**：
     * SQLite持久化存储
     * 连接池和事务管理
     * 索引优化提升性能
   - **情感分析系统**：
     * 实时情绪识别
     * 情感变化追踪
     * 个性化回应策略

4. **错误处理和恢复**
   - **网络请求重试机制**：
     * 指数退避策略
     * 速率限制自适应
     * 超时控制和请求取消
   - **WebSocket连接管理**：
     * 自动心跳检测
     * 不活跃连接清理
     * 断线重连机制
</details>

<details>
<summary><b>项目结构</b></summary>

```
AI_toy/
├── app/
│   ├── agent/             # AI代理相关代码
│   │   ├── companion_agent.py  # AI伴侣核心逻辑
│   │   ├── tools.py            # 工具函数集
│   │   └── prompts.py          # 提示词模板
│   ├── core/             # 核心功能
│   │   ├── memory.py     # 记忆管理
│   │   ├── speech.py     # 语音处理
│   │   └── state.py      # 状态管理
│   └── web/              # Web服务
│       ├── server.py     # WebSocket服务器
│       └── static/       # 静态资源
├── config/               # 配置文件
│   └── settings.py       # 全局设置
├── ssl/                  # SSL证书
├── data/                 # 数据存储
├── database.py           # 数据库管理
├── main.py               # Web服务入口
├── cli.py                # 命令行客户端
├── check_config.py       # 配置检查工具
├── view_memories.py      # 记忆查看工具
└── requirements.txt      # 依赖列表
```
</details>

<details>
<summary><b>优化特性</b></summary>

1. **内存管理优化**
   - 使用连接池管理数据库连接
   - 上下文管理器确保资源释放
   - JSON序列化替代不安全的eval()

2. **性能优化**
   - 数据库索引提升查询速度
   - WebSocket连接池管理
   - 不活跃连接自动清理

3. **错误处理增强**
   - 全局异常处理机制
   - 详细的日志记录
   - 用户友好的错误提示

4. **网络请求管理**
   - 自适应重试策略
   - 速率限制处理
   - 超时控制

5. **用户体验改进**
   - 命令行进度条显示
   - 详细的状态提示
   - 错误恢复自动化
</details>

## 🔍 常见问题与解决方案

<details>
<summary><b>连接问题</b></summary>

**问题**: 无法连接到服务器

**解决方案**: 
- 运行`python check_config.py`检查配置
- 确保SSL证书配置正确
- 检查端口8001是否被占用
- 验证WebSocket连接状态
</details>

<details>
<summary><b>音频问题</b></summary>

**问题**: 无法录制或播放音频

**解决方案**:
- 检查麦克风和扬声器设备
- 使用`python check_config.py`验证音频设备
- 确认授予浏览器麦克风权限
</details>

<details>
<summary><b>API密钥问题</b></summary>

**问题**: DeepSeek API调用失败

**解决方案**:
- 确认.env文件中有正确的DEEPSEEK_API_KEY
- 验证API密钥未过期
- 检查网络连接状态
</details>

<details>
<summary><b>数据库问题</b></summary>

**问题**: 数据库错误或连接失败

**解决方案**:
- 确保data目录存在且有写入权限
- 检查SQLite安装
- 尝试删除并重新创建数据库文件
</details>

## 🙏 致谢

感谢以下开源项目:
- FastAPI - Web服务框架
- Edge-TTS - 语音合成技术
- DeepSeek API - 大型语言模型服务
- Whisper 模型 - 语音识别
- LangChain 框架 - 对话管理
- SQLite - 轻量级数据库

## 📚 更多资源

- [API文档](docs/api.md)
- [开发指南](docs/development.md)
- [部署文档](docs/deployment.md)

## 📄 许可证

本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。

---

**项目维护者:** [alexzhu0](https://github.com/alexzhu0)

**最后更新:** 2023年12月
