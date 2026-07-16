@echo off
chcp 65001 >nul
echo 正在创建开机自启动任务...
schtasks /Create /TN "AI_ChatBot_Roxy" /TR "python D:\ai beifen\ai-chatbot\main.py" /SC ONSTART /RU SYSTEM /F
echo.
echo 完成！开机后服务会自动启动
echo 如需删除任务，运行：schtasks /Delete /TN "AI_ChatBot_Roxy" /F
pause
