"""
微信适配器 - 支持 Gewechat（iPad协议，推荐）和 OpenClaw

Gewechat 使用方式：
1. 安装 Docker Desktop
2. 运行 Gewechat 容器
3. 扫码登录微信
4. 在本项目设置中配置 Gewechat API 地址
"""

import asyncio
import json
import logging
import uuid
from typing import Optional

import httpx

logger = logging.getLogger("wechat")


class WeChatBridge:
    """微信桥接 - 统一接口，支持 Gewechat 和 OpenClaw"""

    def __init__(self, mode: str = "gewechat", api_base_url: str = "http://localhost:2531",
                 token: str = ""):
        self.mode = mode
        self.api_base = api_base_url.rstrip("/")
        self.token = token
        self.client = httpx.AsyncClient(timeout=30)
        self.running = False

        # Gewechat 专用
        self.app_id = ""
        self.wxid = ""
        # 联系人映射 session_id -> wxid
        self.contacts: dict[str, str] = {}
        # 反向映射
        self._id_to_session: dict[str, str] = {}

        # 回调（支持 async）
        self._msg_callback = None

    def on_message(self, callback):
        """设置消息回调 callback(wxid, content) -> 回复内容
        可以是 async 函数或普通函数"""
        self._msg_callback = callback

    async def _call_msg_callback(self, wxid: str, content: str) -> str | None:
        if self._msg_callback is None:
            return None
        result = self._msg_callback(wxid, content)
        if hasattr(result, '__awaitable__') or hasattr(result, '__await__'):
            result = await result
        return result

    def register_contact(self, session_id: str, wxid: str):
        self.contacts[session_id] = wxid
        self._id_to_session[wxid] = session_id

    # ==================== 消息发送 ====================

    async def send_message(self, to: str, content: str) -> bool:
        if self.mode == "gewechat":
            return await self._gewe_send(to, content)
        else:
            return await self._openclaw_send(to, content)

    async def send_proactive_by_session(self, session_id: str, content: str) -> bool:
        wxid = self.contacts.get(session_id)
        if not wxid:
            logger.warning(f"找不到 {session_id} 的微信联系人")
            return False
        return await self.send_message(wxid, content)

    async def _gewe_send(self, to: str, content: str) -> bool:
        try:
            resp = await self.client.post(
                f"{self.api_base}/v2/api/Message/postText",
                json={"appId": self.app_id, "toWxid": to, "content": content},
                headers={"X-GEWE-TOKEN": self.token},
                timeout=15,
            )
            data = resp.json()
            return data.get("ret") == 200
        except Exception as e:
            logger.error(f"Gewe 发送失败: {e}")
            return False

    async def _openclaw_send(self, to: str, content: str) -> bool:
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            resp = await self.client.post(
                f"{self.api_base}/api/send_msg",
                json={"to": to, "content": content, "type": "text"},
                headers=headers,
            )
            return resp.json().get("status") == "ok"
        except Exception as e:
            logger.error(f"OpenClaw 发送失败: {e}")
            return False

    # ==================== Gewechat 登录流程 ====================

    async def get_qrcode(self) -> Optional[str]:
        """获取登录二维码（base64）"""
        if self.mode != "gewechat":
            return None
        try:
            resp = await self.client.get(
                f"{self.api_base}/v2/api/Login/getLoginQrCode",
                params={"appId": self.app_id or ""},
                timeout=15,
            )
            data = resp.json()
            if data.get("ret") == 200:
                result = data.get("data", {})
                self.app_id = result.get("appId") or self.app_id
                return result.get("qrData")
        except Exception as e:
            logger.error(f"获取二维码失败: {e}")
        return None

    async def check_login(self) -> bool:
        """检查登录状态"""
        if self.mode != "gewechat" or not self.app_id:
            return False
        try:
            resp = await self.client.post(
                f"{self.api_base}/v2/api/Login/checkLogin",
                json={"appId": self.app_id},
                headers={"X-GEWE-TOKEN": self.token},
                timeout=15,
            )
            data = resp.json()
            if data.get("ret") == 200:
                login_data = data.get("data", {})
                if login_data.get("loginInfo") or login_data.get("wxid"):
                    self.wxid = login_data.get("wxid", "")
                    return True
        except Exception as e:
            logger.error(f"检查登录失败: {e}")
        return False

    async def get_profile(self) -> Optional[dict]:
        """获取登录账号信息"""
        if self.mode != "gewechat" or not self.app_id:
            return None
        try:
            resp = await self.client.post(
                f"{self.api_base}/v2/api/Personal/getProfile",
                json={"appId": self.app_id},
                headers={"X-GEWE-TOKEN": self.token},
                timeout=15,
            )
            data = resp.json()
            return data.get("data")
        except:
            return None

    # ==================== 消息轮询（兼容 OpenClaw） ====================

    async def _poll_openclaw(self):
        last_id = 0
        while self.running:
            try:
                headers = {}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"
                resp = await self.client.get(
                    f"{self.api_base}/api/messages",
                    params={"last_id": last_id},
                    headers=headers,
                    timeout=30,
                )
                data = resp.json()
                if data.get("status") == "ok":
                    for msg in data.get("messages", []):
                        last_id = max(last_id, msg.get("id", 0))
                        if self._msg_callback and msg.get("type") == "text":
                            reply = self._msg_callback(msg.get("from", ""), msg.get("content", ""))
                            if reply:
                                await self._openclaw_send(msg.get("from", ""), reply)
            except httpx.TimeoutException:
                pass
            except Exception as e:
                logger.error(f"轮询异常: {e}")
                await asyncio.sleep(5)
            await asyncio.sleep(1)

    # ==================== 主动消息循环 ====================

    _proactive_handler = None

    def set_proactive_handler(self, handler):
        """设置主动消息处理器，支持 async"""
        self._proactive_handler = handler

    async def _call_proactive(self, session_id: str) -> str | None:
        if self._proactive_handler is None:
            return None
        result = self._proactive_handler(session_id)
        if hasattr(result, '__awaitable__') or hasattr(result, '__await__'):
            result = await result
        return result

    async def _proactive_loop(self):
        while self.running:
            try:
                if self._proactive_handler and self.contacts:
                    for session_id in list(self.contacts.keys()):
                        reply = await self._call_proactive(session_id)
                        if reply:
                            await self.send_proactive_by_session(session_id, reply)
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"主动消息异常: {e}")
            for _ in range(300):
                if not self.running:
                    return
                await asyncio.sleep(1)

    # ==================== 启动/停止 ====================

    async def start(self):
        self.running = True
        logger.info(f"微信适配器启动 (模式={self.mode})")

        if self.mode == "gewechat":
            if self.app_id:
                ok = await self.check_login()
                if ok:
                    profile = await self.get_profile()
                    name = (profile or {}).get("nickName", "未知")
                    logger.info(f"微信已登录: {name} (wxid={self.wxid})")
                else:
                    logger.warning("微信未登录，请在 WebUI 扫码")
            # Gewechat 通过回调接收消息，不需要轮询
            # 只运行主动消息循环
            await self._proactive_loop()
        else:
            # OpenClaw 轮询模式
            async def run():
                poll = asyncio.create_task(self._poll_openclaw())
                pro = asyncio.create_task(self._proactive_loop())
                await asyncio.gather(poll, pro)
            await run()

    async def stop(self):
        self.running = False
        await self.client.aclose()
        logger.info("微信适配器已停止")
