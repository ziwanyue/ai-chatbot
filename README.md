# 🤖 AI ChatBot - 本地部署 AI 聊天机器人

一个支持**自定义角色性格**、**接入微信**的本地 AI 聊天机器人，支持多种 LLM 后端。

## ✨ 功能特点

- 🎭 **自定义角色性格** - 通过 Web 界面创建角色，自定义性格、说话风格、背景故事
- 💬 **接入微信** - 通过 OpenClaw 协议接入个人微信，在微信中与 AI 对话
- 🧠 **多 LLM 后端** - 支持 DeepSeek、千问、Kimi、硅基流动等 OpenAI 兼容 API，也支持 Ollama 本地模型
- 📦 **本地部署** - 数据完全存储在本地，隐私安全
- 🔌 **Web 管理界面** - 可视化配置、角色管理、聊天记录管理

## 🚀 快速开始

### 前置要求

- Python 3.10+
- 一个 LLM API Key（DeepSeek / 千问 / 硅基流动 等）

### 安装运行

```bash
# 1. 进入项目目录
cd ai-chatbot

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python main.py
```

首次启动会自动创建配置文件 `config.yaml`，编辑配置文件填入你的 API Key 后重新启动即可。

或者通过 Web 界面 `http://localhost:8000/settings` 配置。

### 使用 Ollama 本地模型

1. 安装 [Ollama](https://ollama.ai)
2. 下载模型：`ollama pull qwen2.5:7b`
3. 在设置页面选择 Ollama 并填入模型名

## 🎭 创建角色

1. 访问 `http://localhost:8000/characters`
2. 点击「新建角色」
3. 填写角色名称、系统提示词（描述性格/说话风格/背景故事）
4. 保存后在聊天页面选择该角色即可

### 角色配置示例

```yaml
name: 小樱
prompt: |
  你是我的温柔女友，叫小樱，18岁。
  性格特点：
  - 甜美黏人，喜欢撒娇
  - 略带傲娇，偶尔口是心非
  - 非常关心对方，会主动嘘寒问暖

  说话风格：
  - 语气活泼可爱，多用语气词（啦、呀、嘛、哦）
  - 适当使用颜文字和表情
  - 会记得之前聊过的内容
greeting: 主人~想你了！🥰 今天有没有想我呀？
temperature: 0.9
```

## 💬 接入微信

### 方式一：OpenClaw API（推荐）

1. 在手机上安装微信（最新版本，iOS >= 8.0.70 / Android >= 8.0.69）
2. 运行 OpenClaw 微信桥接服务
3. 在本项目 `http://localhost:8000/settings` 中启用微信，填写 API 地址
4. 扫码登录后即可在微信中与 AI 对话

### 方式二：其他微信桥接服务

本项目微信适配器采用插件化设计，支持对接任意 HTTP API 形式的微信桥接服务。

## ⚙️ 配置

所有配置通过 Web 界面 `http://localhost:8000/settings` 管理：

| 配置项 | 说明 |
|--------|------|
| LLM 提供商 | OpenAI 兼容 API / Ollama |
| API Key | 你的 LLM API 密钥 |
| API 地址 | 如 `https://api.deepseek.com` |
| 模型名 | 如 `deepseek-chat`、`qwen-max` |
| 温度 | 控制创造力的参数 (0-2) |
| 微信开关 | 启用/禁用微信接入 |

## 🐳 Docker 部署

```bash
docker compose up -d
```

## 📁 项目结构

```
ai-chatbot/
├── main.py              # 主入口
├── config.yaml          # 配置文件
├── requirements.txt     # Python 依赖
├── characters/          # 角色定义（YAML）
│   ├── default.yaml
│   ├── sweet_girlfriend.yaml
│   └── sensei.yaml
├── core/                # 核心逻辑
│   ├── llm.py           # LLM 提供商抽象
│   ├── character.py     # 角色管理系统
│   ├── memory.py        # 对话记忆
│   └── chat.py          # 聊天引擎
├── webui/               # Web 管理界面
│   ├── routes.py        # 路由
│   └── templates/       # HTML 模板
├── platforms/           # 平台适配器
│   └── wechat.py        # 微信适配器
└── data/                # 运行数据
```

## 📝 开源协议

MIT License
