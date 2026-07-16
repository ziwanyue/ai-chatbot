@echo off
chcp 65001 >nul
cd /d "D:\ai beifen\ai-chatbot"
echo 正在启动 AI ChatBot...
echo 服务启动后请访问：http://localhost:8000
echo 按 Ctrl+C 可停止服务
python main.py
pause
