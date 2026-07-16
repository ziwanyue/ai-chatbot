# AI ChatBot NAS 部署指南

## 群晖 Synology (Docker)

### 1. 启用 Docker
控制面板 → Docker → 启用

### 2. 创建 docker-compose.yml

在 NAS 上创建文件夹 `/volume1/docker/ai-chatbot`，然后创建文件：

```yaml
version: '3'
services:
  ai-chatbot:
    image: python:3.12-slim
    container_name: ai-chatbot
    working_dir: /app
    volumes:
      - ./app:/app
      - ./config:/root/.config/ai-chatbot
    ports:
      - "8000:8000"
    command: >
      bash -c "pip install fastapi uvicorn pyyaml jinja2 edge-tts aiohttp &&
               python main.py"
    restart: always
    networks:
      - chatbot_net

networks:
  chatbot_net:
    driver: bridge
```

### 3. 上传代码

将 `ai-chatbot` 文件夹整个上传到 `/volume1/docker/ai-chatbot/app`

### 4. 启动

```bash
cd /volume1/docker/ai-chatbot
docker-compose up -d
```

### 5. 设置开机自启

```bash
# 添加到 DSM 开机启动
echo "docker start ai-chatbot" >> /usr/local/etc/rc.local
```

---

## 威联通 QNAP (Container Station)

### 1. 安装 Container Station
App Center → 搜索并安装 Container Station

### 2. 创建容器

```bash
docker run -d \
  --name ai-chatbot \
  --restart always \
  -p 8000:8000 \
  -v /share/Container/ai-chatbot/app:/app \
  python:3.12-slim \
  bash -c "cd /app && pip install fastapi uvicorn pyyaml jinja2 edge-tts aiohttp && python main.py"
```

---

## 极空间/绿联等国产 NAS

### 方式一：Docker（如果支持）
同群晖步骤

### 方式二：Python 直接运行

1. SSH 登录 NAS
2. 安装 Python（如果没预装）
3. 上传代码到 `/share/ai-chatbot`
4. 创建启动脚本：

```bash
#!/bin/bash
cd /share/ai-chatbot
export PATH="/opt/python3/bin:$PATH"
python3 main.py
```

5. 添加到开机启动任务

---

## 配置外网访问

### 方式一：NAS 自带 DDNS
- 群晖：QuickConnect 或 DDNS
- 威联通：myQNAPcloud
- 极空间：极连接
- 绿联：绿联云连接

### 方式二：端口转发
1. 登录路由器
2. 添加端口转发规则：
   - 外部端口：8000
   - 内部 IP：NAS 的 IP
   - 内部端口：8000

### 方式三：反向代理（推荐）
使用 Nginx Proxy Manager 或 NAS 自带的反向代理

---

## 注意事项

1. **确认 NAS 支持 Python 3.10+**
2. **确保有足够内存**（建议 2GB 以上）
3. **配置防火墙**允许 8000 端口
4. **定期备份** memory 和 characters 目录
