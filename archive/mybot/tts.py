"""
小米 MiMo TTS 封装模块。

对外暴露两个接口：
1. synthesize_with_voice: 使用指定音色合成语音
2. design_voice:          通过文字描述定制音色，并生成预览音频

两个接口都支持两种输出格式（通过 output_format 控制）：
- "wav":    将音频写入 output_path 指定的 WAV 文件，返回保存路径
- "base64": 不落盘，直接返回 base64 字符串（WAV 格式）
"""

import base64
import io
import os
from typing import Literal, Optional

import numpy as np
import soundfile as sf
from openai import OpenAI

__all__ = ["synthesize_with_voice", "design_voice", "OutputFormat"]

DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
DEFAULT_VOICE = "Chloe"
DEFAULT_SAMPLE_RATE = 24000

OutputFormat = Literal["wav", "base64"]


def _get_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> OpenAI:
    """构造 OpenAI 客户端。优先使用显式参数，其次使用环境变量。"""
    return OpenAI(
        api_key=api_key or os.environ.get("MIMO_API_KEY"),
        base_url=base_url or DEFAULT_BASE_URL,
    )


def _ensure_parent_dir(path: str) -> None:
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)


def _validate_output_args(output_format: OutputFormat, output_path: Optional[str]) -> None:
    if output_format not in ("wav", "base64"):
        raise ValueError(f"Unsupported output_format: {output_format!r}, expected 'wav' or 'base64'")
    if output_format == "wav" and not output_path:
        raise ValueError("output_path is required when output_format='wav'")


def _deliver_wav(
    wav_bytes: bytes,
    output_format: OutputFormat,
    output_path: Optional[str],
) -> str:
    """根据 output_format 将 WAV 字节交付：写文件或返回 base64 字符串。"""
    if output_format == "wav":
        assert output_path is not None  # 已在 _validate_output_args 中校验
        _ensure_parent_dir(output_path)
        with open(output_path, "wb") as f:
            f.write(wav_bytes)
        return output_path
    # base64
    return base64.b64encode(wav_bytes).decode("ascii")


def synthesize_with_voice(
    text: str,
    output_path: Optional[str] = None,
    voice: str = DEFAULT_VOICE,
    *,
    output_format: OutputFormat = "wav",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    使用指定音色将文本合成为语音。

    :param text: 要合成的文本内容
    :param output_path: 音频文件保存路径（仅当 output_format="wav" 时必需）
    :param voice: 使用的音色（默认 "Chloe"）
    :param output_format: 输出格式，"wav" 写文件 / "base64" 返回 base64 字符串
    :param api_key: 可选，覆盖默认的 API Key
    :param base_url: 可选，覆盖默认的 base_url
    :return: 当 output_format="wav" 时返回文件路径；当 output_format="base64" 时返回 base64 字符串
    """
    _validate_output_args(output_format, output_path)
    client = _get_client(api_key, base_url)

    completion = client.chat.completions.create(
        model="mimo-v2.5-tts",
        messages=[
            {"role": "user", "content": "Please read the following text aloud."},
            {"role": "assistant", "content": text},
        ],
        audio={
            "format": "pcm16",
            "voice": voice,
        },
        stream=True,
    )

    # 24kHz PCM16LE mono audio
    collected_chunks: np.ndarray = np.array([], dtype=np.float32)

    for chunk in completion:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        audio = getattr(delta, "audio", None)

        if audio is not None:
            assert isinstance(audio, dict), f"Expected audio to be a dict, got {type(audio)}"
            pcm_bytes = base64.b64decode(audio["data"])
            np_pcm = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            collected_chunks = np.concatenate((collected_chunks, np_pcm))

    # 将 PCM 编码为 WAV 字节
    buffer = io.BytesIO()
    sf.write(buffer, collected_chunks, samplerate=DEFAULT_SAMPLE_RATE, format="WAV")
    wav_bytes = buffer.getvalue()

    return _deliver_wav(wav_bytes, output_format, output_path)


def design_voice(
    voice_description: str,
    preview_text: str,
    output_path: Optional[str] = None,
    *,
    output_format: OutputFormat = "wav",
    optimize_text_preview: bool = False,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    通过文字描述定制音色，并生成预览音频。

    :param voice_description: 对目标音色的描述（例如 "Give me a young male tone."）
    :param preview_text: 用该音色朗读的预览文本
    :param output_path: 音频文件保存路径（仅当 output_format="wav" 时必需）
    :param output_format: 输出格式，"wav" 写文件 / "base64" 返回 base64 字符串
    :param optimize_text_preview: 是否优化预览文本（默认 True）
    :param api_key: 可选，覆盖默认的 API Key
    :param base_url: 可选，覆盖默认的 base_url
    :return: 当 output_format="wav" 时返回文件路径；当 output_format="base64" 时返回 base64 字符串
    """
    _validate_output_args(output_format, output_path)
    client = _get_client(api_key, base_url)

    completion = client.chat.completions.create(
        model="mimo-v2.5-tts-voicedesign",
        messages=[
            {"role": "user", "content": voice_description},
            {"role": "assistant", "content": preview_text},
        ],
        audio={
            "format": "wav",
            "optimize_text_preview": optimize_text_preview,
        },
    )

    message = completion.choices[0].message

    # 接口返回的 message.audio.data 已是 base64 字符串
    if output_format == "base64":
        return message.audio.data

    wav_bytes = base64.b64decode(message.audio.data)
    return _deliver_wav(wav_bytes, output_format, output_path)
