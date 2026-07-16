"""角色性格系统 - 管理 AI 角色设定"""

import os
import yaml
from typing import Optional

CHARACTERS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "characters")


class Character:
    """角色定义"""

    def __init__(self, name: str, prompt: str, greeting: str = "",
                 description: str = "", model: Optional[str] = None,
                 temperature: Optional[float] = None):
        self.name = name          # 角色名称
        self.prompt = prompt      # 系统提示词 (角色设定核心)
        self.greeting = greeting  # 首次打招呼消息
        self.description = description  # 角色描述（显示用）
        self.model = model           # 可选：为此角色指定模型
        self.temperature = temperature  # 可选：为此角色指定温度

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "greeting": self.greeting,
            "description": self.description,
            "model": self.model,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Character":
        return cls(
            name=d.get("name", "未命名"),
            prompt=d.get("prompt", ""),
            greeting=d.get("greeting", ""),
            description=d.get("description", ""),
            model=d.get("model"),
            temperature=d.get("temperature"),
        )


class CharacterManager:
    """角色管理器 - 负责角色的 CRUD"""

    def __init__(self):
        self._characters: dict[str, Character] = {}
        self._load_characters()

    def _load_characters(self):
        """从 characters/ 目录加载所有角色"""
        os.makedirs(CHARACTERS_DIR, exist_ok=True)
        for fname in os.listdir(CHARACTERS_DIR):
            if fname.endswith((".yaml", ".yml")):
                path = os.path.join(CHARACTERS_DIR, fname)
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "name" in data:
                        char = Character.from_dict(data)
                        self._characters[char.name] = char

    def list_characters(self) -> list[Character]:
        return list(self._characters.values())

    def get(self, name: str) -> Optional[Character]:
        return self._characters.get(name)

    def save(self, character: Character) -> str:
        """保存角色到 YAML 文件, 返回文件名"""
        safe_name = character.name.replace(" ", "_").replace("/", "_")
        path = os.path.join(CHARACTERS_DIR, f"{safe_name}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(character.to_dict(), f, allow_unicode=True, default_flow_style=False)
        self._characters[character.name] = character
        return path

    def delete(self, name: str) -> bool:
        """删除角色"""
        safe_name = name.replace(" ", "_").replace("/", "_")
        path = os.path.join(CHARACTERS_DIR, f"{safe_name}.yaml")
        if os.path.exists(path):
            os.remove(path)
        return self._characters.pop(name, None) is not None


# 内置默认角色
DEFAULT_CHARACTER = Character(
    name="default",
    prompt="""你是一个友好的 AI 助手。请用中文回答用户的问题。
你性格温和、耐心，善于倾听。回答要简洁明了、自然亲切。""",
    greeting="你好！我是你的 AI 助手，有什么可以帮助你的吗？",
    description="友好的默认 AI 助手",
)
