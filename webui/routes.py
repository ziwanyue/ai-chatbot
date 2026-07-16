"""Web UI 路由 - 聊天界面 + 角色管理 + 系统设置"""

import uuid
import yaml
import os
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from core.chat import ChatEngine
from core.character import Character, CharacterManager

router = APIRouter()
import jinja2

_jinja2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
    autoescape=jinja2.select_autoescape(),
    cache_size=0,  # 禁用缓存以兼容当前 Jinja2 版本
)
templates = Jinja2Templates(env=_jinja2_env)

# 挂载音频目录
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
router.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# 在 main 中注入
chat_engine: ChatEngine = None
config: dict = None
config_path: str = None


def get_session_id(request: Request) -> str:
    sid = request.cookies.get("session_id")
    if not sid:
        sid = str(uuid.uuid4())
    return sid


@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    session_id = get_session_id(request)
    character_name = request.query_params.get("character", "default")
    target_session = request.query_params.get("session")

    if target_session:
        session_id = target_session

    # 获取或创建会话
    chat_engine.memory.get_or_create_session(session_id, character_name)

    history = chat_engine.memory.get_history(session_id)
    characters = chat_engine.char_mgr.list_characters()
    sessions = chat_engine.memory.list_sessions(limit=20)
    greeting = chat_engine.get_greeting(character_name) if not history else ""

    return templates.TemplateResponse(request, "chat.html", {
        "session_id": session_id,
        "current_char": character_name,
        "history": history,
        "characters": characters,
        "sessions": sessions,
        "greeting": greeting,
    })


@router.post("/api/chat")
async def api_chat(data: dict):
    session_id = data.get("session_id", str(uuid.uuid4()))
    message = data.get("message", "")
    character_name = data.get("character_name", "default")

    if not message.strip():
        return JSONResponse({"status": "error", "error": "消息不能为空"})

    try:
        reply = await chat_engine.chat(session_id, message, character_name)
        return JSONResponse({
            "status": "ok",
            "reply": reply,
            "session_id": session_id,
        })
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})


@router.delete("/api/chat/{session_id}/clear")
async def clear_history(session_id: str):
    chat_engine.memory.clear_history(session_id)
    return JSONResponse({"status": "ok"})


# === 记忆管理 API ===

@router.get("/api/memory/{session_id}")
async def get_memories(session_id: str):
    from core.memory import LongTermMemory
    ltm = LongTermMemory(session_id)
    memories = ltm.get_all()
    return JSONResponse(memories)


@router.delete("/api/memory/{session_id}/{memory_id}")
async def delete_memory(session_id: str, memory_id: int):
    from core.memory import get_db
    conn = get_db()
    conn.execute("DELETE FROM long_term_memory WHERE id = ? AND session_id = ?",
                 (memory_id, session_id))
    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok"})


# === 角色管理 API ===

@router.get("/characters", response_class=HTMLResponse)
async def characters_page(request: Request):
    characters = chat_engine.char_mgr.list_characters()
    return templates.TemplateResponse(request, "characters.html", {
        "characters": characters,
    })


@router.get("/api/characters")
async def list_characters():
    chars = chat_engine.char_mgr.list_characters()
    return JSONResponse([c.to_dict() for c in chars])


@router.get("/api/characters/{name}")
async def get_character(name: str):
    char = chat_engine.char_mgr.get(name)
    if not char:
        return JSONResponse({"status": "error", "error": "角色不存在"}, status_code=404)
    return JSONResponse(char.to_dict())


@router.post("/api/characters")
async def save_character(data: dict):
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"status": "error", "error": "角色名不能为空"})

    # 如果重命名，先删除旧的
    orig_name = data.get("orig_name")
    if orig_name and orig_name != name:
        chat_engine.char_mgr.delete(orig_name)

    char = Character(
        name=name,
        prompt=data.get("prompt", ""),
        greeting=data.get("greeting", ""),
        description=data.get("description", ""),
        model=data.get("model"),
        temperature=data.get("temperature"),
    )
    chat_engine.char_mgr.save(char)
    return JSONResponse({"status": "ok"})


@router.delete("/api/characters/{name}")
async def delete_character(name: str):
    chat_engine.char_mgr.delete(name)
    return JSONResponse({"status": "ok"})


# === 设置页面 ===

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {
        "config": config,
    })


@router.post("/settings")
async def save_settings(
    request: Request,
    llm_provider: str = Form("openai_compatible"),
    openai_api_key: str = Form(""),
    openai_base_url: str = Form("https://api.deepseek.com"),
    openai_model: str = Form("deepseek-chat"),
    ollama_base_url: str = Form("http://localhost:11434"),
    ollama_model: str = Form("qwen2.5:7b"),
    temperature: float = Form(0.8),
    max_tokens: int = Form(2048),
    wechat_enabled: str = Form("false"),
    wechat_api_url: str = Form("http://localhost:8080"),
    wechat_token: str = Form(""),
):
    new_config = {
        "server": {"host": config.get("server", {}).get("host", "0.0.0.0"),
                    "port": config.get("server", {}).get("port", 8000)},
        "llm": {
            "provider": llm_provider,
            "openai_compatible": {
                "api_key": openai_api_key,
                "base_url": openai_base_url,
                "model": openai_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            "ollama": {
                "base_url": ollama_base_url,
                "model": ollama_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        },
        "character": config.get("character", "default"),
        "memory": config.get("memory", {"max_history": 50}),
        "wechat": {
            "enabled": wechat_enabled == "true",
            "mode": "openclaw_api",
            "openclaw_api": {
                "base_url": wechat_api_url,
                "token": wechat_token,
            },
        },
    }

    # 保存到文件
    if config_path:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(new_config, f, allow_unicode=True, default_flow_style=False)

    # 更新内存中的配置
    config.clear()
    config.update(new_config)

    # 重启 LLM 提供商
    from core.llm import create_llm_provider
    chat_engine.llm = create_llm_provider(config.get("llm", {}))

    return RedirectResponse(url="/settings", status_code=303)


# === OpenAI 兼容 API（供 Cherry Studio / ClawBot 调用） ===

@router.get("/v1/models")
async def list_models():
    """返回可用模型列表"""
    chars = chat_engine.char_mgr.list_characters()
    models = []
    for c in chars:
        models.append({
            "id": f"chatbot-{c.name}",
            "object": "model",
            "created": 0,
            "owned_by": "chatbot",
        })
    return {"object": "list", "data": models}


@router.post("/v1/chat/completions")
async def chat_completions(data: dict):
    """OpenAI 兼容的聊天补全接口"""
    messages = data.get("messages", [])
    model = data.get("model", "chatbot-洛琪希")
    stream = data.get("stream", False)

    # 提取角色名
    character_name = "洛琪希"
    if model.startswith("chatbot-"):
        character_name = model[8:]

    # 提取用户消息
    user_msg = ""
    session_id = f"cherry_{data.get('user', 'default')}"
    for msg in messages:
        if msg["role"] == "user":
            user_msg = msg["content"]
        elif msg["role"] == "system" and msg["content"]:
            pass  # 角色设定由本地管理

    if not user_msg:
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}

    try:
        reply = await chat_engine.chat(session_id, user_msg, character_name)
        return {
            "id": "chatcmpl-" + str(uuid.uuid4()),
            "object": "chat.completion",
            "created": int(__import__("time").time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
        }
    except Exception as e:
        return {
            "error": {"message": str(e), "type": "server_error"},
        }


# === 微信回调 API ===

wechat_bridge_ref = None


@router.post("/api/wechat/callback")
async def wechat_callback(data: dict):
    """Gewechat 消息回调入口"""
    global wechat_bridge_ref
    if not wechat_bridge_ref:
        return {"ret": 200}
    wxid = data.get("wxid", data.get("from", ""))
    content = data.get("content", data.get("Content", ""))
    if wxid and content:
        reply = await wechat_bridge_ref._call_msg_callback(wxid, content)
        if reply:
            await wechat_bridge_ref.send_message(wxid, reply)
    return {"ret": 200}


@router.get("/api/wechat/qrcode")
async def wechat_qrcode():
    """获取 Gewechat 登录二维码"""
    global wechat_bridge_ref
    if not wechat_bridge_ref:
        return JSONResponse({"status": "error", "message": "微信未启动"})
    qr = await wechat_bridge_ref.get_qrcode()
    if qr:
        return JSONResponse({"status": "ok", "qrcode": qr})
    return JSONResponse({"status": "waiting", "message": "等待二维码生成"})


@router.get("/api/wechat/status")
async def wechat_status():
    """检查微信登录状态"""
    global wechat_bridge_ref
    if not wechat_bridge_ref:
        return JSONResponse({"status": "error", "message": "微信未启动"})
    logged_in = await wechat_bridge_ref.check_login()
    if logged_in:
        profile = await wechat_bridge_ref.get_profile()
        return JSONResponse({"status": "ok", "logged_in": True, "profile": profile})
    return JSONResponse({"status": "ok", "logged_in": False})
