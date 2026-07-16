# AI ChatBot Render 部署指南

## 步骤一：准备代码

### 1. 创建 requirements.txt

在 `ai-chatbot` 目录下创建文件：

```
fastapi>=0.100.0
uvicorn>=0.23.0
pyyaml>=6.0
jinja2>=3.1.0
edge-tts>=6.1.0
aiohttp>=3.8.0
```

### 2. 创建 render.yaml

在项目根目录创建 `render.yaml`：

```yaml
services:
  - type: web
    name: ai-chatbot-roxy
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.0
      - key: PORT
        value: 8000
    freePlanAllowed: true
    region: oregon
    autoDeploy: true
```

### 3. 修改 main.py 支持 PORT 环境变量

确保 `main.py` 使用 `$PORT` 环境变量（Render 自动注入）。

---

## 步骤二：上传到 Git

### 方式一：GitHub

```bash
cd D:\ai beifen\ai-chatbot

# 初始化 git
git init
git add .
git commit -m "Initial commit"

# 关联远程仓库（先创建 GitHub 仓库）
git remote add origin https://github.com/你的用户名/ai-chatbot.git
git push -u origin main
```

### 方式二：直接上传
在 Render 界面直接连接 GitHub 仓库

---

## 步骤三：部署到 Render

### 1. 注册/登录 Render
访问 https://render.com 并登录（可用 GitHub 登录）

### 2. 创建服务

1. 点击 **New +** → **Web Service**
2. 连接你的 GitHub 仓库
3. 填写配置：

| 配置项 | 值 |
|--------|-----|
| Name | ai-chatbot-roxy |
| Region | Oregon (免费) |
| Branch | main |
| Root Directory | 留空 |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

### 3. 选择免费计划
选择 **Free** 计划

### 4. 点击 Deploy

---

## 步骤四：配置环境变量

在 Render 控制台 → **Environment** 添加：

```
PORT=8000
```

---

## 步骤五：获取访问地址

部署成功后，你会得到类似这样的地址：

```
https://ai-chatbot-roxy.onrender.com
```

**保存这个网址，随时访问！**

---

## 注意事项 ⚠️

### 免费计划限制

| 限制 | 说明 |
|------|------|
| 每月 750 小时 | 约 25 天，超出会暂停 |
| 休眠 | 15 分钟无访问自动休眠 |
| 唤醒时间 | 首次访问需等待 30-50 秒 |
| 内存 | 512MB |
| CPU | 共享 0.1 CPU |

### 解决休眠问题

**方案一：使用监控服务唤醒**
```bash
# 使用 UptimeRobot (免费)
每 5 分钟访问一次 https://ai-chatbot-roxy.onrender.com
```

**方案二：升级到付费计划**
$7/月，不休眠

---

## 自动唤醒脚本（UptimeRobot 配置）

1. 注册 https://uptimerobot.com
2. Add New Monitor
3. 配置：
   - Monitor Type: HTTP(s)
   - Friendly Name: ai-chatbot
   - URL: https://你的服务.onrender.com
   - Monitoring Interval: 5 minutes

---

##  Troubleshooting

### 构建失败
检查 `requirements.txt` 格式和依赖版本

### 启动失败
查看 Render 控制台 **Logs** 标签页

### 无法访问
- 检查是否休眠（Logs 会显示 Stopped）
- 检查防火墙/安全组

---

## 成本估算

| 项目 | 费用 |
|------|------|
| Render 免费计划 | ¥0 |
| UptimeRobot 免费 | ¥0 |
| API 调用费 | 按量（如 DeepSeek） |
| **总计** | **¥0 + API 费** |

---

## 快速部署命令

```bash
# 1. 创建必要文件
cd D:\ai beifen\ai-chatbot

# 2. 创建 requirements.txt
echo fastapi uvicorn pyyaml jinja2 edge-tts aiohttp > requirements.txt

# 3. 创建 render.yaml
# (复制上面的内容)

# 4. 推送到 GitHub
git add requirements.txt render.yaml
git commit -m "Add Render config"
git push

# 5. 在 Render 连接 GitHub 仓库即可
```
