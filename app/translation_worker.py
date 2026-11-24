from __future__ import annotations

import json
import traceback
import urllib.error
import urllib.request
from pathlib import Path


class HttpModelClient:
    """Small child-process client for the already running local GGUF server."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def create_chat_completion(self, *, messages, temperature=0.15, max_tokens=2048,
                               timeout=900):
        payload = json.dumps({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 503:
                raise RuntimeError(detail[:500] or "模型仍在加载") from exc
            raise RuntimeError(f"CUDA 推理服务错误：{detail[:500]}") from exc


def run_translation_process(
    source: str,
    base_url: str,
    model_name: str,
    request: dict,
    output_dir: str,
    progress_queue,
    cancel_event,
) -> None:
    try:
        from app.translator import translate_pdf

        client = HttpModelClient(base_url)

        def progress(done: int, total: int, detail: str) -> None:
            progress_queue.put(("progress", int(done), int(total), str(detail)))

        outputs = translate_pdf(
            Path(source), client, model_name, request, Path(output_dir),
            progress, cancel_event,
        )
        progress_queue.put(("completed", outputs))
    except BaseException as exc:
        if cancel_event.is_set():
            progress_queue.put(("cancelled", "翻译已取消"))
        else:
            progress_queue.put(("failed", str(exc), traceback.format_exc()))
