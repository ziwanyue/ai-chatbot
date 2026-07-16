"""语音合成引擎 - 使用 Microsoft Edge TTS"""

import os
import asyncio
import edge_tts
from typing import Optional

# 输出目录
AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


class TTSEngine:
    """TTS 引擎 - 将文本转换为语音"""

    # 中文语音选项
    # 小原好美声线特点：温柔、清澈、感情细腻但不外露
    VOICE_ZH_XIAOXIAO = "zh-CN-XiaoxiaoNeural"   # 女声，温暖 (最接近小原好美的洛琪希)
    VOICE_ZH_XIAOYI = "zh-CN-XiaoyiNeural"       # 女声，活泼
    VOICE_ZH_YUNXI = "zh-CN-YunxiNeural"         # 男声
    VOICE_ZH_YUNYANG = "zh-CN-YunyangNeural"     # 男声，新闻播报
    VOICE_ZH_XIAOMENG = "zh-CN-XiaomengNeural"   # 女声，活泼

    def __init__(self, voice: str = VOICE_ZH_XIAOXIAO, rate: str = "-10%", pitch: str = "-2Hz", volume: str = "+10%"):
        """
        初始化 TTS 引擎

        Args:
            voice: 语音 ID
            rate: 语速 (+0% 正常，+20% 更快，-20% 更慢)
            pitch: 音调 (+0Hz 正常，+10Hz 更高，-10Hz 更低)
            volume: 音量 (+0% 正常，+20% 更大，-20% 更小)
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    async def synthesize(self, text: str, output_file: str) -> str:
        """
        将文本转换为语音并保存为文件

        Args:
            text: 要转换的文本
            output_file: 输出文件路径

        Returns:
            输出文件路径
        """
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicate.save(output_file)
        return output_file

    async def synthesize_roxy(self, text: str, session_id: str = "default") -> str:
        """
        为洛琪希角色合成语音（参考小原好美声线）

        小原好美演绎洛琪希的特点：
        - 温柔清澈的声线
        - 感情细腻但不外露（被要求压抑感情）
        - 外表幼小但内心成熟
        - 教学时条理清晰，坚定的温柔

        Args:
            text: 要转换的文本
            session_id: 会话 ID（用于生成唯一的文件名）

        Returns:
            输出文件路径
        """
        # 使用 Xiaoxiao 温暖声线，更接近小原好美的温柔特质
        communicate = edge_tts.Communicate(
            text,
            self.VOICE_ZH_XIAOXIAO,
            rate="-10%",   # 语速稍慢，表现温柔和沉稳
            pitch="-2Hz",  # 音调略低，表现成年人的成熟感（洛琪希实际是成年人）
            volume="+5%",  # 音量稍大，保证清晰度
        )

        # 生成唯一的文件名
        import hashlib
        import time
        timestamp = str(int(time.time() * 1000))
        hash_id = hashlib.md5(f"{session_id}_{timestamp}".encode()).hexdigest()[:8]
        output_file = os.path.join(AUDIO_DIR, f"roxy_{hash_id}.mp3")

        await communicate.save(output_file)
        return output_file

    @staticmethod
    async def list_voices() -> list[dict]:
        """获取所有可用的语音列表"""
        voices = await edge_tts.list_voices()
        # 过滤出中文语音
        zh_voices = [v for v in voices if v.get("Locale", "").startswith("zh-")]
        return zh_voices


# 全局 TTS 引擎实例（洛琪希专用）
_roxy_tts: Optional[TTSEngine] = None


def get_roxy_tts() -> TTSEngine:
    """获取洛琪希专用的 TTS 引擎实例（参考小原好美声线）"""
    global _roxy_tts
    if _roxy_tts is None:
        _roxy_tts = TTSEngine(
            voice=TTSEngine.VOICE_ZH_XIAOXIAO,
            rate="-10%",
            pitch="-2Hz",
            volume="+5%",
        )
    return _roxy_tts
