"""对话记忆管理 - 聊天历史 + 长期记忆 + 事实提取"""

import json
import os
import sqlite3
import re
from datetime import datetime
from typing import Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "chatbot.db")


def get_db() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            character_name TEXT DEFAULT 'default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id);

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            character_name TEXT DEFAULT 'default',
            platform TEXT DEFAULT 'web',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            fact_type TEXT DEFAULT 'info',
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_recalled TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            recall_count INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_memory_session ON long_term_memory(session_id);
        CREATE INDEX IF NOT EXISTS idx_memory_type ON long_term_memory(fact_type);

        CREATE TABLE IF NOT EXISTS active_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_proactive TIMESTAMP,
            inactive_alert_sent INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


class LongTermMemory:
    """长期记忆 - 记住用户说过的重要信息"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        init_db()

    def save_fact(self, fact_type: str, content: str):
        """保存一条事实记忆"""
        conn = get_db()
        # 检查是否已存在相似内容（简单去重）
        existing = conn.execute(
            "SELECT id, content FROM long_term_memory WHERE session_id = ? AND content = ?",
            (self.session_id, content),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE long_term_memory SET last_recalled = CURRENT_TIMESTAMP, recall_count = recall_count + 1 WHERE id = ?",
                (existing["id"],),
            )
        else:
            conn.execute(
                "INSERT INTO long_term_memory (session_id, fact_type, content) VALUES (?, ?, ?)",
                (self.session_id, fact_type, content),
            )
        conn.commit()
        conn.close()

    def get_relevant(self, limit: int = 15) -> list[str]:
        """获取最相关的记忆（按召回频率和时间排序）"""
        conn = get_db()
        rows = conn.execute(
            "SELECT content FROM long_term_memory WHERE session_id = ? ORDER BY recall_count DESC, last_recalled DESC LIMIT ?",
            (self.session_id, limit),
        ).fetchall()
        conn.close()
        return [r["content"] for r in rows]

    def get_all(self) -> list[dict]:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM long_term_memory WHERE session_id = ? ORDER BY recall_count DESC",
            (self.session_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def build_memory_prompt(self) -> str:
        """构建记忆上下文，注入到系统提示词中"""
        memories = self.get_relevant(limit=12)
        if not memories:
            return ""
        text = "\n".join(f"- {m}" for m in memories)
        return f'\n\n【洛琪希记得的关于你的事】\n{text}\n（以上信息是从记忆中提取的，用自然的方式融入对话中，不要刻意罗列，也不用在回复中提到「根据记忆」之类的话。）'


class ConversationMemory:
    """会话记忆管理器"""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        init_db()

    def get_history(self, session_id: str) -> list[dict]:
        conn = get_db()
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def add_message(self, session_id: str, role: str, content: str,
                    character_name: str = "default"):
        conn = get_db()
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, character_name) VALUES (?, ?, ?, ?)",
            (session_id, role, content, character_name),
        )
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, character_name, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (session_id, character_name),
        )
        conn.commit()
        conn.close()
        self._trim_history(session_id)

    def _trim_history(self, session_id: str):
        if self.max_history <= 0:
            return
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) as c FROM conversations WHERE session_id = ?",
            (session_id,),
        ).fetchone()["c"]
        if count > self.max_history:
            delete_count = count - self.max_history
            conn.execute(
                "DELETE FROM conversations WHERE id IN (SELECT id FROM conversations WHERE session_id = ? ORDER BY id LIMIT ?)",
                (session_id, delete_count),
            )
            conn.commit()
        conn.close()

    def clear_history(self, session_id: str):
        conn = get_db()
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def get_or_create_session(self, session_id: str, character_name: str = "default",
                              platform: str = "web") -> dict:
        conn = get_db()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            conn.close()
            return dict(row)
        conn.execute(
            "INSERT INTO sessions (id, character_name, platform) VALUES (?, ?, ?)",
            (session_id, character_name, platform),
        )
        conn.commit()
        conn.close()
        return {"id": session_id, "character_name": character_name, "platform": platform}

    def list_sessions(self, limit: int = 50) -> list[dict]:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str):
        conn = get_db()
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.execute("DELETE FROM long_term_memory WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def get_conversation_summary(self, session_id: str, limit: int = 10) -> str:
        """获取最近的对话摘要（用于提取事实的原始材料）"""
        conn = get_db()
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        conn.close()
        lines = []
        for r in reversed(rows):
            who = "你" if r["role"] == "user" else "洛琪希"
            content = r["content"][:150]
            lines.append(f"{who}: {content}")
        return "\n".join(lines)


class MemoryExtractor:
    """从对话中提取关键信息，存入长期记忆"""

    def __init__(self, session_id: str):
        self.ltm = LongTermMemory(session_id)

    def extract_from_message(self, user_message: str):
        """从用户消息中提取事实"""
        message_lower = user_message.lower()

        # 名字
        name_patterns = [
            r"(?:我叫|我是|我的名字是|可以叫我|叫我)(.+?)(?:[，。！？\,\.\!\?\s]|$)",
            r"(?:叫我|喊我)(.+?)(?:[，。！？\,\.\!\?\s吧]|$)",
        ]
        for p in name_patterns:
            m = re.search(p, user_message)
            if m:
                name = m.group(1).strip()[:20]
                if name and len(name) > 1:
                    self.ltm.save_fact("name", f"对方的名字是{name}")

        # 年龄
        age_patterns = [
            r"(?:我|今年|已经)(\d+)(?:岁|岁了)",
            r"(\d+)(?:岁|岁了)",
        ]
        for p in age_patterns:
            m = re.search(p, user_message)
            if m:
                age = m.group(1)
                self.ltm.save_fact("info", f"对方{age}岁")

        # 性别
        if any(w in user_message for w in ["我是男的", "我是男生", "我是男的", "男生", "男儿身"]):
            self.ltm.save_fact("info", "对方是男性")
        elif any(w in user_message for w in ["我是女的", "我是女生", "女生", "女孩子"]):
            self.ltm.save_fact("info", "对方是女性")

        # 工作
        work_patterns = [
            r"(?:我(?:是做|在|从事))(.{1,20}(?:工作|行业|的))",
            r"(?:我的工作|我的职业|我干)(?:是|的)(.{1,20})",
        ]
        for p in work_patterns:
            m = re.search(p, user_message)
            if m:
                work = m.group(1).strip()[:30]
                self.ltm.save_fact("info", f"对方的工作是{work}")

        # 位置（匹配"我住在X"或"我在X"等模式）
        loc_match = re.search(r"(?:我(?:住在|在|来自|在))(.{2,4}(?:市|省|区))", user_message)
        if loc_match:
            city = loc_match.group(1).strip()[:20]
            self.ltm.save_fact("info", f"对方住在{city}")

        # 喜好
        like_patterns = [
            r"(?:我(?:喜欢|爱|爱吃|爱喝|最爱)(.{1,30}))",
            r"(?:我(?:最喜欢|特别喜欢|很喜欢)(.{1,30}))",
        ]
        for p in like_patterns:
            m = re.search(p, user_message)
            if m:
                like = m.group(1).strip()[:30]
                self.ltm.save_fact("preference", f"对方喜欢{like}")

        # 状态
        state_patterns = [
            r"(?:我(?:今天|最近|这两天)(.{1,40}(?:了|的|。|！|？|\.|!|\?|$)))",
        ]
        for p in state_patterns:
            m = re.search(p, user_message)
            if m:
                state = m.group(1).strip()[:40]
                self.ltm.save_fact("status", f"对方最近的状态：{state}")

        # 提到的重要事件（包含"了"的完成式陈述）
        event_markers = ["去了", "买了", "做了", "吃了", "喝了", "玩了", "看了", "完成了", "通过了", "参加了"]
        for marker in event_markers:
            if marker in user_message:
                idx = user_message.index(marker)
                start = max(0, idx - 10)
                end = min(len(user_message), idx + 30)
                snippet = user_message[start:end].strip()[:40]
                if len(snippet) > 5:
                    self.ltm.save_fact("event", f"对方{snippet}")


class ScheduleManager:
    """活跃度管理 - 追踪用户活跃状态"""

    @staticmethod
    def update_active(session_id: str):
        conn = get_db()
        conn.execute("""
            INSERT INTO active_schedule (session_id, last_active, inactive_alert_sent)
            VALUES (?, CURRENT_TIMESTAMP, 0)
            ON CONFLICT(session_id) DO UPDATE SET last_active = CURRENT_TIMESTAMP, inactive_alert_sent = 0
        """, (session_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_inactive_sessions(hours: int = 4) -> list[Tuple[str, float]]:
        """获取超过指定小时未活跃的会话"""
        conn = get_db()
        rows = conn.execute("""
            SELECT s.id, s.character_name,
                   CAST(julianday('now') - julianday(a.last_active) AS REAL) * 24 AS hours_inactive
            FROM active_schedule a
            JOIN sessions s ON s.id = a.session_id
            WHERE hours_inactive >= ?
              AND a.inactive_alert_sent = 0
              AND s.character_name != 'default'
            ORDER BY hours_inactive DESC
        """, (hours,)).fetchall()
        conn.close()
        return [(r["id"], r["hours_inactive"]) for r in rows]

    @staticmethod
    def mark_alert_sent(session_id: str):
        conn = get_db()
        conn.execute("UPDATE active_schedule SET inactive_alert_sent = 1, last_proactive = CURRENT_TIMESTAMP WHERE session_id = ?",
                     (session_id,))
        conn.commit()
        conn.close()
