"""AI Chat Client — 复用用户已配置的翻译服务 API Key 实现论文问答和摘要"""

import json
import requests
from ui.config_manager import UserConfigManager

# 可用于 chat completion 的服务列表（按优先级排序）
# (显示名, 默认 base_url, 是否需要 API Key)
CHAT_SERVICES = [
    ("DeepSeek",         "https://api.deepseek.com/v1",               True),
    ("OpenAI",           "https://api.openai.com/v1",                 True),
    ("Zhipu 智谱",      "https://open.bigmodel.cn/api/paas/v4",      True),
    ("Qwen 通义千问",   "https://dashscope.aliyuncs.com/compatible-mode/v1", True),
    ("Groq",             "https://api.groq.com/openai/v1",            True),
    ("Silicon 硅基流动", "https://api.siliconflow.cn/v1",             True),
    ("Grok",             "https://api.x.ai/v1",                       True),
    ("Ollama 本地",      "http://localhost:11434/v1",                  False),
    ("OpenAI 兼容",     "",                                           True),
]


def detect_service():
    """自动检测第一个可用的 chat completion 服务，返回 dict 或 None。
    返回: {"name", "base_url", "api_key", "model"} 或 None
    """
    cfg = UserConfigManager.load()
    for name, default_url, needs_key in CHAT_SERVICES:
        api_raw = cfg.get(f"api_{name}", "")
        api_key = UserConfigManager.decode_sensitive(api_raw) if api_raw else ""
        model = cfg.get(f"model_{name}", "")
        url = cfg.get(f"url_{name}", "") or default_url

        if needs_key and not api_key:
            continue
        if not url:
            continue
        if not model:
            # 给个默认模型
            defaults = {
                "DeepSeek": "deepseek-chat", "OpenAI": "gpt-4o-mini",
                "Zhipu 智谱": "glm-4-flash", "Groq": "llama-3.3-70b-versatile",
                "Ollama 本地": "qwen2.5:7b", "Grok": "grok-2-mini",
                "Qwen 通义千问": "qwen-turbo",
            }
            model = defaults.get(name, "")
            if not model:
                continue

        return {"name": name, "base_url": url.rstrip("/"), "api_key": api_key, "model": model}
    return None


def detect_assistant_service():
    """检测 AI 助手服务：优先使用独立配置，否则 fallback 到翻译服务。
    返回: {"name", "base_url", "api_key", "model"} 或 None
    """
    cfg = UserConfigManager.load()
    if cfg.get("assistant_custom", False):
        svc_name = cfg.get("assistant_service", "")
        api_raw = cfg.get("assistant_api_key", "")
        api_key = UserConfigManager.decode_sensitive(api_raw) if api_raw else ""
        model = cfg.get("assistant_model", "")
        url = cfg.get("assistant_url", "")
        # 从 CHAT_SERVICES 获取默认 URL
        if not url:
            for name, default_url, _ in CHAT_SERVICES:
                if name == svc_name:
                    url = default_url
                    break
        if url and model:
            return {"name": svc_name, "base_url": url.rstrip("/"),
                    "api_key": api_key, "model": model}
    # fallback: 使用翻译服务配置
    return detect_service()


def chat_completion(messages: list, service: dict = None, timeout: int = 60) -> str:
    """调用 OpenAI 兼容 chat/completions 接口，返回文本。"""
    svc = service or detect_assistant_service()
    if not svc:
        raise RuntimeError("未配置可用的 AI 服务。请在设置中配置 API Key（如 DeepSeek、OpenAI 等）")

    url = f"{svc['base_url']}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if svc["api_key"]:
        headers["Authorization"] = f"Bearer {svc['api_key']}"

    payload = {
        "model": svc["model"],
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def chat_completion_stream(messages: list, service: dict = None, timeout: int = 120):
    """流式调用，yield 文本片段。"""
    svc = service or detect_assistant_service()
    if not svc:
        raise RuntimeError("未配置可用的 AI 服务。请在设置中配置 API Key（如 DeepSeek、OpenAI 等）")

    url = f"{svc['base_url']}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if svc["api_key"]:
        headers["Authorization"] = f"Bearer {svc['api_key']}"

    payload = {
        "model": svc["model"],
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": True,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True)
    resp.raise_for_status()

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk == "[DONE]":
            break
        try:
            obj = json.loads(chunk)
            delta = obj.get("choices", [{}])[0].get("delta", {})
            text = delta.get("content", "")
            if text:
                yield text
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
