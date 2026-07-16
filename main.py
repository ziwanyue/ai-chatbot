"""
AI ChatBot - 本地部署的 AI 聊天机器人
支持自定义角色性格、接入微信、多种 LLM 后端
"""

import os
import sys
import yaml
import logging
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Windows GBK 终端兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

# 确保项目根目录在路径中
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import create_llm_provider
from core.chat import ChatEngine
from core.memory import init_db, ScheduleManager, LongTermMemory

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chatbot")


def load_config(path: str = None) -> dict:
    """加载配置文件"""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.exists(path):
        # 创建默认配置
        default = {
            "server": {"host": "0.0.0.0", "port": 8000},
            "llm": {
                "provider": "openai_compatible",
                "openai_compatible": {
                    "api_key": "",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "qwen2.5:7b",
                    "temperature": 0.8,
                    "max_tokens": 2048,
                },
            },
            "character": "default",
            "memory": {"max_history": 50},
            "wechat": {
                "enabled": False,
                "mode": "gewechat",
                "gewechat": {
                    "api_url": "http://localhost:2531",
                    "token": "",
                },
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(default, f, allow_unicode=True, default_flow_style=False)
        return default

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_app(cfg: dict, cfg_path: str) -> FastAPI:
    """创建 FastAPI 应用"""
    # 初始化数据库
    init_db()

    # 创建 LLM 提供商
    llm_provider = create_llm_provider(cfg.get("llm", {}))

    # 创建聊天引擎
    engine = ChatEngine(llm_provider, cfg)

    # 注入到路由模块
    import webui.routes as routes
    routes.chat_engine = engine
    routes.config = cfg
    routes.config_path = cfg_path

    from webui.routes import router as web_router

    wechat_bridge = None

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        nonlocal wechat_bridge
        if cfg.get("wechat", {}).get("enabled"):
            wc = cfg["wechat"]
            mode = wc.get("mode", "native")

            async def handle_wechat_msg(wxid: str, content: str) -> str | None:
                content = content.strip()
                if not content:
                    return None
                session_id = f"wechat_{wxid}"
                ScheduleManager.update_active(session_id)
                logger.info(f"微信消息 from {wxid}: {content[:30]}")
                try:
                    return await engine.chat(session_id, content)
                except Exception as e:
                    logger.error(f"处理微信消息失败: {e}")
                    return None

            if mode == "native":
                from platforms.wechat_native import WeChatNativeBridge
                wechat_bridge = WeChatNativeBridge()
                wechat_bridge.msg_callback = handle_wechat_msg
                asyncio.create_task(wechat_bridge.start())
                logger.info("微信原生桥接已启动（基于 UI Automation）")

            elif mode == "gewechat":
                from platforms.wechat import WeChatBridge
                wechat_bridge = WeChatBridge(
                    mode="gewechat",
                    api_base_url=wc.get("gewechat", {}).get("api_url", "http://localhost:2531"),
                    token=wc.get("gewechat", {}).get("token", ""),
                )
                import webui.routes as routes
                routes.wechat_bridge_ref = wechat_bridge
                wechat_bridge.on_message(handle_wechat_msg)

                async def handle_proactive(session_id: str) -> str | None:
                    try:
                        ltm = LongTermMemory(session_id)
                        memories = ltm.get_relevant(limit=5)
                        context = ""
                        if memories:
                            context = f"关于对方你知道这些信息：{'；'.join(memories)}。"
                        context += "现在对方有一段时间没和你说话了。自然地发一条消息过去。"
                        reply = await engine.chat_proactive(session_id, context)
                        ScheduleManager.mark_alert_sent(session_id)
                        return reply
                    except Exception as e:
                        logger.error(f"主动消息失败: {e}")
                        return None

                wechat_bridge.set_proactive_handler(handle_proactive)
                asyncio.create_task(wechat_bridge.start())
                logger.info("Gewechat 适配器已启动")

        yield

        if wechat_bridge:
            wechat_bridge.stop()
        logger.info("AI ChatBot 已关闭")

    # 创建 FastAPI 应用
    app = FastAPI(title="AI ChatBot", version="1.0.0", lifespan=_lifespan)
    app.include_router(web_router)

    return app


def main():
    # 加载配置
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg = load_config(cfg_path)

    # 显示启动信息
    server_cfg = cfg.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8000)
    llm_cfg = cfg.get("llm", {})

    banner = f"""
{'='*48}
  AI ChatBot - 本地部署 AI 聊天机器人
{'='*48}
  LLM 提供商: {llm_cfg.get('provider', 'openai_compatible')}"""
    if llm_cfg.get("provider") == "openai_compatible":
        banner += f"""
  模型: {llm_cfg.get('openai_compatible', {}).get('model', '?')}
  API: {llm_cfg.get('openai_compatible', {}).get('base_url', '?')}"""
    elif llm_cfg.get("provider") == "ollama":
        banner += f"""
  模型: {llm_cfg.get('ollama', {}).get('model', '?')}"""
    banner += f"""
  微信: {'已启用' if cfg.get('wechat', {}).get('enabled') else '未启用'}
  Web 管理: http://localhost:{port}
  配置文件: {cfg_path}
{'='*48}
  如果要使用自定义角色，请在 Web 界面中创建
  或直接编辑 characters/ 目录下的 YAML 文件
{'='*48}
"""
    print(banner, flush=True)

    # 创建并运行应用
    app = create_app(cfg, cfg_path)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
