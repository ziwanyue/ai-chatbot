"""
Windows 原生微信桥接 - 基于 UI Automation
不需要 Docker，不需要 MySQL，直接在 Windows 上运行。

原理：通过 Windows UI Automation 与微信 PC 客户端交互
- 监测新消息（从聊天列表读取）
- 自动回复（复制文本 → 粘贴到输入框 → 发送）

使用前提：
1. 微信 PC 客户端已登录
2. 微信窗口不能最小化到托盘（可以普通最小化）
"""

import asyncio
import logging
import re
import time
from typing import Optional

import pywinauto
from pywinauto.timings import wait_until
import pyperclip

logger = logging.getLogger("wechat_bridge")


class WeChatUIAutomation:
    """基于 UI Automation 的微信桥接"""

    def __init__(self):
        self.app = None
        self.running = False
        self._last_msg_time = time.time()
        self._known_messages: set[str] = set()
        self.msg_callback = None  # async callback(wxid, content) -> reply
        self.my_name = ""  # 当前微信登录用户的昵称

    def connect(self) -> bool:
        """连接到正在运行的微信"""
        try:
            self.app = pywinauto.Application(backend='uia').connect(title='微信', timeout=5)
            main_wnd = self.app.window(title='微信')
            if main_wnd.exists():
                logger.info("已连接到微信")
                # 尝试获取自己的昵称
                try:
                    self.my_name = main_wnd.child_window(auto_id="com.tencent.wework:id/f2v").window_text()
                except:
                    pass
                return True
        except Exception as e:
            logger.error(f"连接微信失败: {e}")
        return False

    def get_chat_list(self) -> list[dict]:
        """获取聊天列表"""
        try:
            main_wnd = self.app.window(title='微信')
            chat_list = main_wnd.child_window(auto_id="com.tencent.wework:id/f2v")
            if not chat_list.exists():
                return []

            items = chat_list.descendants()
            chats = []
            for item in items:
                try:
                    name = item.window_text()
                    if name and name != self.my_name:
                        chats.append({"name": name, "element": item})
                except:
                    pass
            return chats
        except:
            return []

    def get_last_message(self, chat_name: str) -> Optional[str]:
        """获取某个聊天的最新一条消息"""
        try:
            main_wnd = self.app.window(title='微信')
            # 点击聊天
            chat_item = main_wnd.child_window(title=chat_name, control_type="ListItem")
            if not chat_item.exists():
                return None
            chat_item.click_input()

            # 获取消息列表
            msg_list = main_wnd.child_window(auto_id="com.tencent.wework:id/ek1")
            if not msg_list.exists():
                return None

            msgs = msg_list.descendants()
            for msg in reversed(msgs):
                try:
                    text = msg.window_text()
                    if text and len(text) > 1 and text != self.my_name:
                        return text
                except:
                    pass
        except:
            pass
        return None

    def send_message(self, chat_name: str, text: str) -> bool:
        """向指定聊天发送消息"""
        try:
            main_wnd = self.app.window(title='微信')
            # 点击聊天
            chat_item = main_wnd.child_window(title=chat_name, control_type="ListItem")
            if not chat_item.exists():
                return False
            chat_item.click_input()
            time.sleep(0.3)

            # 找到输入框
            edit = main_wnd.child_window(auto_id="com.tencent.wework:id/e1d")
            if not edit.exists():
                # 尝试其他可能的 ID
                edit = main_wnd.child_window(control_type="Edit")
            if not edit.exists():
                return False

            # 输入消息
            edit.click_input()
            pyperclip.copy(text)
            edit.send_keys("^v")
            time.sleep(0.2)
            edit.send_keys("{ENTER}")
            logger.info(f"已发送消息到 {chat_name}: {text[:30]}...")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def _monitor_loop(self):
        """轮询新消息"""
        while self.running:
            try:
                chats = self.get_chat_list()
                for chat in chats[:5]:  # 只检查前5个聊天
                    msg = self.get_last_message(chat["name"])
                    if msg:
                        msg_key = f"{chat['name']}:{msg}"
                        if msg_key not in self._known_messages:
                            self._known_messages.add(msg_key)
                            # 限制记忆大小
                            if len(self._known_messages) > 200:
                                self._known_messages.clear()

                            logger.info(f"收到消息 from {chat['name']}: {msg}")

                            # 不回复自己发送的消息
                            if chat["name"] == self.my_name:
                                continue

                            if self.msg_callback:
                                reply = self.msg_callback(chat["name"], msg)
                                if reply:
                                    # 如果 reply 是 coroutine，需要 await
                                    if asyncio.iscoroutine(reply):
                                        reply = await reply
                                    if reply:
                                        self.send_message(chat["name"], reply)
            except Exception as e:
                logger.error(f"监测异常: {e}")

            await asyncio.sleep(2)

    def start(self, loop: asyncio.AbstractEventLoop):
        """启动监测（在事件循环中运行）"""
        self.running = True
        asyncio.run_coroutine_threadsafe(self._monitor_loop(), loop)

    def stop(self):
        self.running = False


def create_bridge():
    """创建并初始化微信桥接"""
    bridge = WeChatUIAutomation()
    if bridge.connect():
        return bridge
    return None
