# AI ChatBot 云服务器部署指南

## 1. 准备云服务器

### 腾讯云轻量应用服务器
- 价格：约 ¥99/月（2 核 2G3M 带宽）
- 系统：Ubuntu 22.04 或 CentOS 7+
- 地域：选择离你近的（如上海、广州）

### 配置要求
- CPU: 2 核以上
- 内存：2GB 以上
- 带宽：3Mbps 以上
- 存储：20GB 以上

---

## 2. 上传代码到服务器

### 方式一：使用 Git
```bash
# 在服务器上
git clone <你的仓库地址>
cd ai-chatbot
```

### 方式二：使用 SCP 上传
```bash
# 在本地电脑
scp -r D:\ai beifen\ai-chatbot root@<服务器 IP>:/root/
```

---

## 3. 服务器环境配置

```bash
# 安装 Python 3.10+
sudo apt update
sudo apt install python3 python3-pip -y

# 安装依赖
cd /root/ai-chatbot
pip3 install -r requirements.txt

# 安装 edge-tts
pip3 install edge-tts
```

### requirements.txt 内容：
```
fastapi
uvicorn
pyyaml
jinja2
edge-tts
aiohttp
```

---

## 4. 修改配置

### 修改 config.yaml
```yaml
server:
  host: 0.0.0.0  # 允许外部访问
  port: 8000
```

### 开放防火墙端口
```bash
# 腾讯云安全组添加入站规则
# 端口：8000，协议：TCP，来源：0.0.0.0/0
```

---

## 5. 后台运行服务

### 方式一：使用 systemd（推荐）

创建服务文件：
```bash
sudo nano /etc/systemd/system/ai-chatbot.service
```

内容：
```ini
[Unit]
Description=AI ChatBot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ai-chatbot
ExecStart=/usr/bin/python3 /root/ai-chatbot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl start ai-chatbot
sudo systemctl enable ai-chatbot  # 开机自启
sudo systemctl status ai-chatbot  # 查看状态
```

### 方式二：使用 nohup
```bash
nohup python3 main.py > chatbot.log 2>&1 &
```

### 方式三：使用 screen
```bash
screen -S chatbot
python3 main.py
# 按 Ctrl+A 再按 D 退出 screen
# 恢复：screen -r chatbot
```

---

## 6. 访问服务

在浏览器访问：
```
http://<服务器公网 IP>:8000
```

---

## 7. 可选：配置域名和 HTTPS

### 使用 Nginx 反向代理
```bash
sudo apt install nginx -y
```

Nginx 配置 (`/etc/nginx/sites-available/ai-chatbot`)：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 使用 Let's Encrypt 配置 HTTPS
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

---

## 8. 成本估算

| 项目 | 费用 |
|------|------|
| 云服务器（2 核 2G3M） | ¥99/月 |
| 域名（可选） | ¥60/年 |
| SSL 证书 | 免费（Let's Encrypt） |
| **总计** | **约 ¥105/月** |

---

## 快速部署脚本

保存为 `deploy.sh` 并在服务器运行：

```bash
#!/bin/bash
echo "=== AI ChatBot 一键部署脚本 ==="

# 安装依赖
apt update && apt install python3 python3-pip nginx -y

# 安装 Python 依赖
pip3 install fastapi uvicorn pyyaml jinja2 edge-tts aiohttp

# 创建 systemd 服务
cat > /etc/systemd/system/ai-chatbot.service << 'EOF'
[Unit]
Description=AI ChatBot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/ai-chatbot
ExecStart=/usr/bin/python3 /root/ai-chatbot/main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl start ai-chatbot
systemctl enable ai-chatbot

echo "部署完成！访问 http://<服务器 IP>:8000"
```

---

## 注意事项

1. **API 调用费用**：使用阿里云/DeepSeek 等 API 会产生调用费用
2. **流量费用**：云服务器超出免费额度后按流量计费
3. **数据备份**：定期备份 `memory/` 和 `characters/` 目录
