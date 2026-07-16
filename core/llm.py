"""LLM 提供商抽象层 - 支持 OpenAI 兼容 API 和 Ollama"""

from abc import ABC, abstractmethod
from typing import Optional
import httpx
from openai import OpenAI


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        ...

    @abstractmethod
    async def chat_stream(self, messages: list[dict], **kwargs):
        ...


class OpenAICompatibleProvider(LLMProvider):
    """支持 OpenAI 兼容 API (DeepSeek, 千问, Kimi, 硅基流动 等)"""

    def __init__(self, api_key: str, base_url: str, model: str,
                 temperature: float = 0.8, max_tokens: int = 2048):
        self._api_key = api_key
        self._base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def chat(self, messages: list[dict], **kwargs) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return resp.choices[0].message.content or ""

    async def chat_stream(self, messages: list[dict], **kwargs):
        client = self._get_client()
        stream = client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


class OllamaProvider(LLMProvider):
    """本地 Ollama 提供商"""

    def __init__(self, base_url: str, model: str,
                 temperature: float = 0.8, max_tokens: int = 2048):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(self, messages: list[dict], **kwargs) -> str:
        import asyncio
        import urllib.request
        import json as _json
        payload = _json.dumps({
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            },
            "stream": False,
        }).encode()
        for attempt in range(6):
            try:
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = _json.loads(resp.read())
                    return data["message"]["content"]
            except Exception:
                if attempt < 5:
                    await asyncio.sleep(10)
        raise Exception("Ollama 连接失败，请确认 Ollama 正在运行")

    async def chat_stream(self, messages: list[dict], **kwargs):
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "options": {
                        "temperature": kwargs.get("temperature", self.temperature),
                        "num_predict": kwargs.get("max_tokens", self.max_tokens),
                    },
                    "stream": True,
                },
                timeout=300,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        import json
                        try:
                            data = json.loads(line)
                            if content := data.get("message", {}).get("content"):
                                yield content
                        except:
                            pass


def create_llm_provider(config: dict) -> LLMProvider:
    """工厂方法 - 根据配置创建 LLM 提供商"""
    provider_type = config.get("provider", "openai_compatible")
    if provider_type == "ollama":
        oc = config.get("ollama", {})
        return OllamaProvider(
            base_url=oc.get("base_url", "http://localhost:11434"),
            model=oc.get("model", "qwen2.5:7b"),
            temperature=oc.get("temperature", 0.8),
            max_tokens=oc.get("max_tokens", 2048),
        )
    # 默认: openai_compatible
    oc = config.get("openai_compatible", {})
    return OpenAICompatibleProvider(
        api_key=oc.get("api_key", ""),
        base_url=oc.get("base_url", "https://api.deepseek.com"),
        model=oc.get("model", "deepseek-chat"),
        temperature=oc.get("temperature", 0.8),
        max_tokens=oc.get("max_tokens", 2048),
    )
