"""核心聊天引擎 - 整合 LLM + 角色 + 记忆 + 长期记忆 + 语音合成"""

from core.llm import LLMProvider
from core.character import CharacterManager, Character
from core.memory import ConversationMemory, LongTermMemory, MemoryExtractor, ScheduleManager
from core.tts import get_roxy_tts


class ChatEngine:
    """聊天引擎 - 处理完整的对话逻辑"""

    def __init__(self, llm_provider: LLMProvider, config: dict):
        self.llm = llm_provider
        self.config = config
        self.char_mgr = CharacterManager()
        max_history = config.get("memory", {}).get("max_history", 50)
        self.memory = ConversationMemory(max_history=max_history)
        # 语音支持
        self.tts_enabled = config.get("tts", {}).get("enabled", False)
        self.tts_engine = get_roxy_tts() if self.tts_enabled else None

    def _build_messages(self, session_id: str, user_message: str,
                        character: Character) -> list[dict]:
        """构建发送给 LLM 的消息列表"""
        messages = []

        # 1. 系统提示词（角色设定）
        system_prompt = character.prompt

        # 2. 注入长期记忆
        ltm = LongTermMemory(session_id)
        memory_context = ltm.build_memory_prompt()
        if memory_context:
            system_prompt += memory_context

        # 3. 注入活跃度上下文（如果是主动发起的消息）
        if hasattr(self, '_proactive_context') and self._proactive_context:
            system_prompt += f"\n\n【上下文提示】{self._proactive_context}"

        messages.append({"role": "system", "content": system_prompt})

        # 4. 历史消息
        history = self.memory.get_history(session_id)
        messages.extend(history)

        # 5. 当前用户消息
        messages.append({"role": "user", "content": user_message})

        return messages

    async def chat(self, session_id: str, user_message: str,
                   character_name: str = "default", generate_voice: bool = True) -> dict:
        """
        发送消息并获取回复

        Returns:
            dict: {"text": 回复文本，"voice": 语音文件路径（如果有）}
        """
        character = self.char_mgr.get(character_name) or self.char_mgr.get("default")
        if character is None:
            from core.character import DEFAULT_CHARACTER
            character = DEFAULT_CHARACTER

        # 提取事实
        extractor = MemoryExtractor(session_id)
        extractor.extract_from_message(user_message)

        # 构建消息
        self._proactive_context = None
        messages = self._build_messages(session_id, user_message, character)

        # 调用 LLM
        llm_kwargs = {}
        if character.temperature is not None:
            llm_kwargs["temperature"] = character.temperature
        if character.model:
            llm_kwargs["model"] = character.model

        reply = await self.llm.chat(messages, **llm_kwargs)

        # 保存到会话记忆
        self.memory.add_message(session_id, "user", user_message, character_name)
        self.memory.add_message(session_id, "assistant", reply, character_name)

        # 生成语音（如果是洛琪希角色且启用了 TTS）
        voice_file = None
        if self.tts_enabled and self.tts_engine and generate_voice and character_name == "洛琪希":
            try:
                voice_file = await self.tts_engine.synthesize_roxy(reply, session_id)
            except Exception as e:
                print(f"TTS 失败：{e}")

        ScheduleManager.update_active(session_id)

        return {"text": reply, "voice": voice_file}

    async def chat_proactive(self, session_id: str, proactive_context: str,
                             character_name: str = "default", generate_voice: bool = True) -> dict:
        """主动发起消息（不是对用户消息的回复）"""
        character = self.char_mgr.get(character_name) or self.char_mgr.get("default")
        if character is None:
            from core.character import DEFAULT_CHARACTER
            character = DEFAULT_CHARACTER

        # 构建一个空消息来触发主动回复
        self._proactive_context = proactive_context
        prompt = f"[主动发起对话] {proactive_context} 根据以上情境，以洛琪希的身份自然地发一条消息给对方。不要用括号描述动作，直接说话。长度适中，语气自然。"
        messages = self._build_messages(session_id, prompt, character)

        llm_kwargs = {}
        if character.temperature is not None:
            llm_kwargs["temperature"] = max(0.7, character.temperature)
        if character.model:
            llm_kwargs["model"] = character.model

        reply = await self.llm.chat(messages, **llm_kwargs)

        # 保存到会话记忆
        self.memory.add_message(session_id, "assistant", reply, character_name)
        self._proactive_context = None

        # 生成语音
        voice_file = None
        if self.tts_enabled and self.tts_engine and generate_voice and character_name == "洛琪希":
            try:
                voice_file = await self.tts_engine.synthesize_roxy(reply, session_id)
            except Exception as e:
                print(f"TTS 失败：{e}")

        return {"text": reply, "voice": voice_file}

    async def chat_stream(self, session_id: str, user_message: str,
                          character_name: str = "default", generate_voice: bool = True):
        """
        发送消息并获取流式回复

        Yields:
            dict: {"text": 文本片段，"voice": 语音文件路径（最后一条）}
        """
        character = self.char_mgr.get(character_name) or self.char_mgr.get("default")
        if character is None:
            from core.character import DEFAULT_CHARACTER
            character = DEFAULT_CHARACTER

        # 提取事实
        extractor = MemoryExtractor(session_id)
        extractor.extract_from_message(user_message)

        self.memory.add_message(session_id, "user", user_message, character_name)
        self._proactive_context = None

        messages = self._build_messages(session_id, user_message, character)

        llm_kwargs = {}
        if character.temperature is not None:
            llm_kwargs["temperature"] = character.temperature
        if character.model:
            llm_kwargs["model"] = character.model

        full_reply = ""
        voice_file = None
        async for chunk in self.llm.chat_stream(messages, **llm_kwargs):
            full_reply += chunk
            yield {"text": chunk, "voice": None}

        if full_reply:
            self.memory.add_message(session_id, "assistant", full_reply, character_name)
            ScheduleManager.update_active(session_id)

            # 生成语音
            if self.tts_enabled and self.tts_engine and generate_voice and character_name == "洛琪希":
                try:
                    voice_file = await self.tts_engine.synthesize_roxy(full_reply, session_id)
                except Exception as e:
                    print(f"TTS 失败：{e}")

        yield {"text": "", "voice": voice_file}

    def get_greeting(self, character_name: str = "default") -> str:
        character = self.char_mgr.get(character_name)
        if character and character.greeting:
            return character.greeting
        return "你好！有什么可以帮助你的吗？"
