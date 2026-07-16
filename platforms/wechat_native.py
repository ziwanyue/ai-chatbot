"""
Windows 原生微信桥接 - 基于 UI Automation
不需要 Docker/MySQL，只需要微信 PC 客户端在运行。
"""

import asyncio
import logging
import re
import time
from typing import Optional
import os

logger = logging.getLogger("wechat_native")


class WeChatNativeBridge:
    """
    通过 Windows UI Automation 操作微信 PC 客户端。
    需先登录微信并保持窗口开启（可最小化）。
    """

    def __init__(self):
        self.running = False
        self.msg_callback = None
        self._known_msgs: set = set()
        self._uia = None
        self._main_wnd = None
        self._wx_name = ""

    def _init_uia(self):
        """延迟导入 uiautomation"""
        if self._uia is None:
            import uiautomation as uia
            self._uia = uia
        return self._uia

    def connect(self) -> bool:
        """连接到微信主窗口"""
        try:
            uia = self._init_uia()
            self._main_wnd = uia.WindowControl(Name="微信")
            if not self._main_wnd.Exists(3, 1):
                # 试试英文名
                self._main_wnd = uia.WindowControl(Name="WeChat")
            if self._main_wnd.Exists(1, 1):
                self._main_wnd.SetActive()
                logger.info("已连接到微信")
                # 获取自己的昵称
                try:
                    name_ctrl = self._main_wnd.Name
                    self._wx_name = self._main_wnd.Name
                except:
                    self._wx_name = ""
                return True
        except Exception as e:
            logger.error(f"连接微信失败: {e}")
        return False

    def get_chat_names(self) -> list[str]:
        """获取聊天列表中的联系人名称"""
        try:
            uia = self._init_uia()
            wnd = uia.WindowControl(Name="微信")
            if not wnd.Exists(0, 1):
                return []
            # 聊天列表通常在左侧 ListControl 中
            list_ctrl = wnd.ListControl()
            if not list_ctrl.Exists(0, 1):
                return []
            items = list_ctrl.GetChildren()
            names = []
            for item in items:
                try:
                    name = item.Name
                    if name and name.strip() and name != self._wx_name:
                        names.append(name.strip())
                except:
                    pass
            return names
        except:
            return []

    def get_last_message(self, chat_name: str) -> Optional[str]:
        """获取指定聊天的最后一条消息"""
        try:
            uia = self._init_uia()
            wnd = uia.WindowControl(Name="微信")
            if not wnd.Exists(0, 1):
                return None
            # 点击聊天
            chat_item = wnd.ListItemControl(Name=chat_name)
            if not chat_item.Exists(0, 1):
                return None
            chat_item.Click()
            time.sleep(0.3)

            # 获取消息列表区域
            # 通常在聊天区域的 ListControl 或 ListItemControl 中
            msg_items = wnd.ListControl().GetChildren()
            if not msg_items:
                return None

            # 取最后几条消息中的最后一条
            for item in reversed(msg_items):
                try:
                    text = item.Name
                    if text and len(text) > 1:
                        return text
                except:
                    pass
        except:
            pass
        return None

    def send_message(self, chat_name: str, text: str) -> bool:
        """发送消息"""
        try:
            uia = self._init_uia()
            wnd = uia.WindowControl(Name="微信")
            if not wnd.Exists(0, 1):
                return False
            # 点击聊天
            chat_item = wnd.ListItemControl(Name=chat_name)
            if not chat_item.Exists(0, 1):
                return False
            chat_item.Click()
            time.sleep(0.3)

            # 找到输入框
            edit = wnd.EditControl()
            if not edit.Exists(0, 1):
                return False
            edit.Click()
            time.sleep(0.1)
            edit.SendKeys(text)
            time.sleep(0.1)
            edit.SendKeys("{Enter}")
            logger.info(f"已发送 -> {chat_name}: {text[:30]}...")
            return True
        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False

    async def start(self):
        """启动消息监测循环"""
        if not self.connect():
            logger.error("无法连接微信，请先打开微信并登录")
            return

        self.running = True
        logger.info("微信原生桥接已启动")
        self._main_wnd.SetActive()

        while self.running:
            try:
                names = self.get_chat_names()
                for name in names[:3]:  # 只检查前几个聊天
                    msg = self.get_last_message(name)
                    if msg:
                        key = f"{name}:{msg}"
                        if key not in self._known_msgs:
                            self._known_msgs.add(key)
                            if len(self._known_msgs) > 500:
                                self._known_msgs.clear()
                            logger.info(f"收到: [{name}] {msg[:30]}")
                            if self.msg_callback:
                                reply = self.msg_callback(name, msg)
                                if asyncio.iscoroutine(reply):
                                    reply = await reply
                                if reply:
                                    self.send_message(name, reply)
            except Exception as e:
                logger.error(f"监测异常: {e}")
            await asyncio.sleep(2)

    def stop(self):
        self.running = False
