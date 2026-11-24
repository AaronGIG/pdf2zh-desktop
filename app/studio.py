from __future__ import annotations

import atexit
import json
import multiprocessing
import os
import queue as queue_module
import re
import shutil
import socket
import subprocess
import threading
import time
import sys
import urllib.error
import urllib.request
import webview
from pathlib import Path


APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Pdf2zhStudio"
MODEL_DIR = APP_DIR / "models"
CONFIG_PATH = APP_DIR / "settings.json"
SERVER_PID_PATH = APP_DIR / "llama-server.pid"
RESOURCE_DIR = (
    Path(sys._MEIPASS) / "resources"
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[1] / "resources"
)
TESSDATA_DIR = RESOURCE_DIR / "tessdata"
if getattr(sys, "frozen", False):
    os.environ["NOTO_FONT_PATH"] = str(RESOURCE_DIR / "SourceHanSerifCN-Regular.ttf")
    os.environ["HF_HUB_OFFLINE"] = "1"
if any(TESSDATA_DIR.glob("*.traineddata")):
    os.environ.setdefault("TESSDATA_PREFIX", str(TESSDATA_DIR))


class _CudaModelClient:
    def __init__(self, process: subprocess.Popen, base_url: str, log_stream,
                 device: str = "CUDA") -> None:
        self._process = process
        self._base_url = base_url.rstrip("/")
        self._log_stream = log_stream
        self.device = device
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def base_url(self) -> str:
        return self._base_url

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
            raise RuntimeError(f"本地推理服务错误：{detail[:500]}") from exc

    def probe(self) -> None:
        response = self.create_chat_completion(
            messages=[{"role": "user", "content": "Reply with OK only."}],
            temperature=0,
            max_tokens=2,
            timeout=30,
        )
        if not isinstance(response, dict) or not response.get("choices"):
            raise RuntimeError("模型服务已启动，但未返回有效的推理结果。")

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        try:
            self._log_stream.close()
        except Exception:
            pass


class Studio:
    def __init__(self) -> None:
        self._window = None
        self._lock = threading.Lock()
        self._model = None
        self._model_path = ""
        self._cuda_server = None
        self._loading = False
        self._loading_detail = ""
        self._loading_started = 0.0
        self._loading_model = ""
        self._loading_process = None
        self._workers = None
        self._translation_process = None
        self._translation_queue = None
        self._translation_cancel = None
        self._translation_active = False
        self._cancel = threading.Event()
        self._jobs: dict[str, dict] = {}
        self._settings = self._read_settings()
        self._output_dir = Path(self._settings.get("outputDir", Path.home() / "Documents" / "Pdf2zhStudio"))
        self._settings.setdefault("maxPagesPerPart", 50)
        self._window_storage = APP_DIR / "webview"
        atexit.register(self._shutdown_cuda_server)

    @staticmethod
    def _read_settings() -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"language": "zh", "format": "dual", "threads": 2,
                    "context": 4096, "ocr": True, "translateTableText": True}

    def _save_settings(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self._settings, ensure_ascii=False, indent=2), encoding="utf-8")

    def _run_on_ui_thread(self, callback):
        """Run native WinForms actions on the thread that owns the window."""
        native = getattr(self._window, "native", None)
        if native is None or not native.InvokeRequired:
            return callback()

        import clr
        from System import Func, Object

        return native.Invoke(Func[Object](callback))

    def _create_file_dialog(self, dialog_type, file_types=()):
        return self._run_on_ui_thread(
            lambda: self._window.gui.create_file_dialog(
                dialog_type, "", False, "", file_types, self._window.uid
            )
        )

    def get_state(self) -> dict:
        import psutil

        models = []
        if MODEL_DIR.exists():
            for path in MODEL_DIR.glob("*.gguf"):
                models.append({"name": path.name, "size": path.stat().st_size, "path": str(path)})
        return {
            "models": models,
            "loadedModel": Path(self._model_path).name if self._model_path else None,
            "device": getattr(self._model, "device", "CPU") if self._model else "CPU",
            "loading": self._loading,
            "loadingDetail": self._loading_detail,
            "loadingElapsed": round(max(0, time.time() - self._loading_started)) if self._loading else 0,
            "loadingModel": self._loading_model or None,
            "settings": self._settings,
            "outputDir": str(self._output_dir), "jobs": list(self._jobs.values()),
            "resource": {"ram": round(psutil.virtual_memory().available / 1024**3, 1), "cores": os.cpu_count() or 4},
        }

    def pick_model(self) -> dict | None:
        selected = self._create_file_dialog(
            webview.OPEN_DIALOG, ("GGUF 模型 (*.gguf)",)
        )
        return self.import_model(selected[0]) if selected else None

    def import_model(self, source: str) -> dict:
        source_path = Path(source)
        if source_path.suffix.lower() != ".gguf" or not source_path.is_file():
            raise ValueError("请选择有效的 .gguf 模型文件。")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        target = MODEL_DIR / source_path.name
        if source_path.resolve() != target.resolve():
            self._notify("正在导入模型", "大文件复制期间可以继续浏览界面。", "info")
            shutil.copy2(source_path, target)
        return {"name": target.name, "size": target.stat().st_size, "path": str(target)}

    def remove_model(self, name: str) -> dict:
        if self._model_path and Path(self._model_path).name == name:
            raise RuntimeError("请先卸载正在使用的模型。")
        target = (MODEL_DIR / name).resolve()
        if target.parent != MODEL_DIR.resolve() or target.suffix != ".gguf":
            raise ValueError("模型路径无效。")
        target.unlink(missing_ok=True)
        return self.get_state()

    def load_model(self, name: str, context: int = 4096) -> dict:
        path = (MODEL_DIR / name).resolve()
        if path.parent != MODEL_DIR.resolve() or not path.is_file():
            raise ValueError("找不到所选模型。")
        with self._lock:
            if self._model is not None or self._loading:
                raise RuntimeError("已有模型正在加载或运行，请先卸载。")
            self._loading = True
            self._loading_started = time.time()
            self._loading_detail = "正在准备模型"
            self._loading_model = path.name
        self._settings["context"] = int(context)
        self._save_settings()
        self._emit("model-loading", {
            "detail": self._loading_detail,
            "elapsed": 0,
            "model": path.name,
        })
        threading.Thread(target=self._load_worker, args=(path, int(context)), daemon=True).start()
        return {"loading": True}

    def _load_worker(self, path: Path, context: int) -> None:
        cuda_server = None
        try:
            from pdf2zh.doclayout import OnnxModel

            if getattr(sys, "frozen", False):
                layout_path = Path(sys._MEIPASS) / "resources" / "doclayout.onnx"
                OnnxModel.from_pretrained = staticmethod(lambda: OnnxModel(str(layout_path)))
            self._set_loading_detail("正在清理旧的本地推理服务")
            self._cleanup_stale_cuda_server(self._cuda_backend_dir())
            self._set_loading_detail("正在启动本地推理服务")
            cuda_server = self._start_cuda_server(path, context)
            with self._lock:
                self._cuda_server = cuda_server
                self._model = cuda_server
                self._model_path = str(path)
            if getattr(cuda_server, "device", "CUDA") == "CPU":
                self._notify(
                    "已切换到 CPU 推理",
                    "没有可用的 CUDA 推理设备，模型已在 CPU 上加载，速度会明显变慢。",
                    "info",
                )
            else:
                self._notify("模型已就绪", f"{path.name} 已加载，可以开始本地翻译。", "success")
        except Exception as exc:
            if cuda_server is not None:
                cuda_server.close()
            self._notify("模型加载失败", str(exc), "error")
        finally:
            with self._lock:
                self._loading = False
                self._loading_detail = ""
                self._loading_started = 0.0
                self._loading_model = ""
                self._loading_process = None
                loaded = bool(self._model)
            self._emit("model-state", {"loaded": loaded, "loading": False})

    def unload_model(self) -> dict:
        if self._loading:
            raise RuntimeError("模型正在加载，请等待当前操作结束。")
        if self._translation_active:
            raise RuntimeError("翻译进行中，不能卸载模型。")
        self._shutdown_cuda_server()
        self._model = None
        self._model_path = ""
        self._notify("模型已卸载", "内存已释放。", "success")
        return {"loadedModel": None}

    @staticmethod
    def _cuda_backend_dir() -> Path | None:
        app_root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        candidates = [app_root / "resources" / "cuda-backend"]
        configured = os.getenv("PDF2ZH_CUDA_BACKEND", "").strip()
        if configured:
            candidates.insert(0, Path(configured))
        candidates.extend([
            Path(r"D:\Program\LM Studio\resources\app\.webpack\bin\extensions\backends")
            / "llama.cpp-win-x86_64-nvidia-cuda-avx2-2.54.0",
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "LM Studio"
            / "resources" / "app" / ".webpack" / "bin" / "extensions" / "backends"
            / "llama.cpp-win-x86_64-nvidia-cuda-avx2-2.54.0",
        ])
        for candidate in candidates:
            server = candidate / "bin" / "llama-server.exe"
            if not server.is_file():
                server = candidate / "llama-server.exe"
            if server.is_file():
                return candidate
        return None

    @staticmethod
    def _server_env(server: Path, vendor: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join(
            str(item)
            for item in (server.parent, vendor, env.get("PATH", ""))
            if item
        )
        return env

    @staticmethod
    def _server_log_tail(log_path: Path, max_bytes: int = 65536) -> str:
        try:
            with log_path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size - max_bytes))
                return stream.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    @classmethod
    def _server_failure_detail(cls, log_path: Path, fallback: str) -> str:
        text = cls._server_log_tail(log_path)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        keywords = (
            "error", "failed", "fail", "out of memory", "cuda", "device",
            "unsupported", "cannot", "unable", "not found", "invalid",
        )
        matches = [
            line for line in lines
            if any(keyword in line.lower() for keyword in keywords)
        ]
        detail = matches[-1] if matches else (lines[-1] if lines else fallback)
        if len(detail) > 700:
            detail = detail[-700:]
        return f"{detail}（日志：{log_path}）"

    @classmethod
    def _list_devices(cls, server: Path, env: dict[str, str]) -> str:
        try:
            completed = subprocess.run(
                [str(server), "--list-devices"],
                cwd=str(server.parent),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            return completed.stdout.decode("utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return ""

    def _start_server_attempt(
        self,
        path: Path,
        context: int,
        server: Path,
        vendor: Path,
        env: dict[str, str],
        device: str,
        device_args: list[str],
    ) -> _CudaModelClient:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        APP_DIR.mkdir(parents=True, exist_ok=True)
        log_path = APP_DIR / "cuda-server.log"
        log_stream = log_path.open("ab")
        marker = (
            f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"device={device} model={path.name} =====\n"
        )
        log_stream.write(marker.encode("utf-8"))
        log_stream.flush()
        command = [
            str(server), "-m", str(path),
            "--host", "127.0.0.1", "--port", str(port),
            *device_args,
            "--ctx-size", str(context),
            "--threads", str(max(1, min((os.cpu_count() or 4) - 1, 12))),
            "--parallel", "1", "--no-webui", "--reasoning", "off",
        ]
        process = None
        try:
            process = subprocess.Popen(
                command,
                cwd=str(server.parent),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            with self._lock:
                self._loading_process = process
            SERVER_PID_PATH.write_text(json.dumps({
                "pid": process.pid,
                "server": str(server.resolve()),
                "model": str(path),
                "device": device,
                "started": time.time(),
            }), encoding="utf-8")
            self._set_loading_detail(f"正在加载 GGUF 模型（{device}）")
            base_url = f"http://127.0.0.1:{port}"
            timeout = 240 if device == "CPU" else 150
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(
                        self._server_failure_detail(
                            log_path, f"{device} 后端进程提前退出"
                        )
                    )
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError(
                    self._server_failure_detail(
                        log_path, f"{device} 模型加载超时"
                    )
                )

            self._set_loading_detail(f"正在验证模型推理能力（{device}）")
            client = _CudaModelClient(process, base_url, log_stream, device)
            last_error = None
            while time.monotonic() < deadline:
                try:
                    client.probe()
                    return client
                except (OSError, urllib.error.URLError) as exc:
                    last_error = exc
                    if process.poll() is not None:
                        raise RuntimeError(
                            self._server_failure_detail(
                                log_path, f"{device} 后端在验证推理时退出"
                            )
                        ) from exc
                    time.sleep(1)
            raise RuntimeError(
                self._server_failure_detail(
                    log_path,
                    f"{device} 推理服务未响应：{last_error}",
                )
            )
        except Exception as exc:
            if process is not None:
                self._terminate_process_handle(process)
                self._remove_server_pid(process.pid)
            try:
                log_stream.close()
            except Exception:
                pass
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(str(exc)) from exc

    def _start_cuda_server(self, path: Path, context: int) -> _CudaModelClient:
        backend = self._cuda_backend_dir()
        if backend is None:
            raise RuntimeError("未找到 CUDA 后端，请确认已打包 cuda-backend 文件。")
        server = backend / "bin" / "llama-server.exe"
        if not server.is_file():
            server = backend / "llama-server.exe"
        vendor = backend / "vendor"
        env = self._server_env(server, vendor)
        force_cpu = os.getenv("PDF2ZH_FORCE_CPU", "").strip().lower() in {
            "1", "true", "yes", "on",
        }
        devices = "" if force_cpu else self._list_devices(server, env)
        has_cuda = bool(re.search(r"\bCUDA\d*\s*:", devices, re.IGNORECASE))
        attempts: list[tuple[str, list[str]]] = []
        if not force_cpu and (has_cuda or not devices.strip()):
            attempts.append((
                "CUDA",
                ["--gpu-layers", "all", "--device", "CUDA0", "--fit", "off"],
            ))
        attempts.append(("CPU", []))

        failures = []
        for device, device_args in attempts:
            try:
                return self._start_server_attempt(
                    path, context, server, vendor, env, device, device_args
                )
            except Exception as exc:
                failures.append(f"{device}: {exc}")
        raise RuntimeError(
            "模型加载失败：可用推理后端均未成功。\n" + "\n".join(failures)[-1600:]
        )

    def _shutdown_cuda_server(self) -> None:
        server = self._cuda_server
        loading_process = self._loading_process
        self._cuda_server = None
        self._loading_process = None
        if server is not None:
            server.close()
            self._remove_server_pid(server.pid)
        elif loading_process is not None:
            self._terminate_process_handle(loading_process)
            self._remove_server_pid(loading_process.pid)

    def _set_loading_detail(self, detail: str) -> None:
        with self._lock:
            if not self._loading:
                return
            self._loading_detail = detail
            elapsed = round(max(0, time.time() - self._loading_started))
            model = self._loading_model
        self._emit("model-loading", {"detail": detail, "elapsed": elapsed, "model": model})

    @staticmethod
    def _terminate_process_handle(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass

    @staticmethod
    def _remove_server_pid(pid: int | None = None) -> None:
        try:
            if not SERVER_PID_PATH.exists():
                return
            if pid is not None:
                data = json.loads(SERVER_PID_PATH.read_text(encoding="utf-8"))
                if int(data.get("pid", -1)) != int(pid):
                    return
            SERVER_PID_PATH.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def _bundled_backend(backend: Path | None) -> bool:
        if backend is None:
            return False
        root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        try:
            return backend.resolve().is_relative_to((root / "resources").resolve())
        except ValueError:
            return False

    def _cleanup_stale_cuda_server(self, backend: Path | None) -> None:
        import psutil

        record = None
        try:
            if SERVER_PID_PATH.exists():
                record = json.loads(SERVER_PID_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = None

        if record:
            pid = record.get("pid")
            try:
                process = psutil.Process(int(pid))
                expected = Path(str(record.get("server", ""))).resolve()
                actual = Path(process.exe()).resolve()
                if actual.name.lower() == "llama-server.exe" and expected == actual:
                    process.terminate()
                    process.wait(timeout=8)
            except (OSError, ValueError, TypeError, psutil.Error):
                pass
            self._remove_server_pid()

        if not self._bundled_backend(backend):
            return
        server = backend / "bin" / "llama-server.exe"
        if not server.is_file():
            server = backend / "llama-server.exe"
        try:
            target = server.resolve()
        except OSError:
            return
        for process in psutil.process_iter(["pid", "exe", "cmdline"]):
            try:
                if process.pid == os.getpid() or not process.info.get("exe"):
                    continue
                if Path(process.info["exe"]).resolve() != target:
                    continue
                cmdline = process.info.get("cmdline") or []
                if "--no-webui" not in cmdline:
                    continue
                process.terminate()
                process.wait(timeout=8)
            except (OSError, ValueError, psutil.Error):
                continue

    def pick_pdf(self) -> dict | None:
        selected = self._create_file_dialog(
            webview.OPEN_DIALOG, ("PDF 文档 (*.pdf)",)
        )
        return self.inspect_pdf(selected[0]) if selected else None

    def inspect_pdf(self, source: str) -> dict:
        import fitz

        path = Path(source)
        with fitz.open(path) as document:
            pages = len(document)
            sample = "".join(document[i].get_text() for i in range(min(3, pages))).strip()
            return {"path": str(path), "name": path.name, "pages": pages,
                    "size": path.stat().st_size, "hasText": bool(sample),
                    "sample": re.sub(r"\s+", " ", sample)[:380], "preview": self._page_preview(path)}

    @staticmethod
    def _page_preview(path: Path) -> str:
        import base64
        import fitz

        with fitz.open(path) as document:
            image = document[0].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False)
            return "data:image/jpeg;base64," + base64.b64encode(image.tobytes("jpeg")).decode()

    def start_translation(self, request: dict) -> dict:
        if self._model is None:
            raise RuntimeError("请先在「本地模型」中加载 GGUF 模型。")
        if self._workers:
            raise RuntimeError("已有翻译任务正在进行。")
        base_url = getattr(self._model, "base_url", "")
        if not base_url:
            raise RuntimeError("本地推理服务未准备好，请重新加载模型。")
        path = Path(request.get("path", ""))
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("请重新选择 PDF 文档。")
        job_id = str(int(time.time() * 1000))
        job = {"id": job_id, "name": path.name, "status": "running", "progress": 0,
               "detail": "正在分析页面与排版", "outputs": [], "started": time.time()}
        self._jobs[job_id] = job
        self._settings.update({"language": request.get("language", "zh"),
                               "format": request.get("format", "dual"),
                               "threads": max(1, min(int(request.get("threads", 2)), 4)),
                               "ocr": bool(request.get("ocr", True)),
                               "translateTableText": bool(request.get("translateTableText", True)),
                               "maxPagesPerPart": max(0, int(request.get("maxPagesPerPart", 50)))})
        self._save_settings()
        self._cancel.clear()
        context = multiprocessing.get_context("spawn")
        progress_queue = context.Queue()
        translation_cancel = context.Event()
        worker = threading.Thread(
            target=self._run_translation_job,
            args=(job_id, str(path), base_url, Path(self._model_path).name,
                  dict(request), str(self._output_dir), progress_queue,
                  translation_cancel, context),
            daemon=True,
        )
        with self._lock:
            self._translation_queue = progress_queue
            self._translation_cancel = translation_cancel
            self._translation_active = True
            self._workers = worker
        try:
            worker.start()
        except Exception:
            with self._lock:
                self._translation_queue = None
                self._translation_cancel = None
                self._translation_active = False
                self._workers = None
            progress_queue.close()
            progress_queue.join_thread()
            raise
        return job

    def _run_translation_job(
        self, job_id: str, source: str, base_url: str, model_name: str,
        request: dict, output_dir: str, progress_queue, translation_cancel,
        context,
    ) -> None:
        process = None
        process_started = False
        try:
            if translation_cancel.is_set():
                raise InterruptedError("翻译已取消")
            from app.translation_worker import run_translation_process

            process = context.Process(
                target=run_translation_process,
                args=(source, base_url, model_name, request, output_dir,
                      progress_queue, translation_cancel),
            )
            with self._lock:
                self._translation_process = process
            process.start()
            process_started = True
            self._translate_worker(job_id, process, progress_queue, translation_cancel)
        except BaseException as exc:
            job = self._jobs.get(job_id)
            if job is not None and job.get("status") == "running":
                cancelled = (isinstance(exc, InterruptedError)
                             or self._cancel.is_set()
                             or translation_cancel.is_set())
                job.update({"status": "cancelled" if cancelled else "failed",
                            "detail": "翻译已取消" if cancelled else str(exc)})
                self._emit("job-updated", job)
                if not cancelled:
                    self._notify("翻译失败", str(exc), "error")
        finally:
            if process_started:
                process.join(timeout=2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
            try:
                progress_queue.close()
                progress_queue.join_thread()
            except (OSError, ValueError):
                pass
            with self._lock:
                if self._translation_process is process:
                    self._translation_process = None
                if self._translation_queue is progress_queue:
                    self._translation_queue = None
                if self._translation_cancel is translation_cancel:
                    self._translation_cancel = None
                self._translation_active = False
                if self._workers is threading.current_thread():
                    self._workers = None

    def _translate_worker(self, job_id: str, process, progress_queue, translation_cancel) -> None:
        terminal = False
        last_progress = -1
        while True:
            try:
                message = progress_queue.get(timeout=0.25)
            except queue_module.Empty:
                if not process.is_alive():
                    break
                continue
            kind = message[0]
            job = self._jobs[job_id]
            if kind == "progress":
                done, total, detail = message[1:]
                current_progress = round(done / max(total, 1) * 100)
                job["progress"] = current_progress
                job["detail"] = detail
                if current_progress != last_progress:
                    self._emit("job-updated", job)
                    last_progress = current_progress
            elif kind == "completed":
                job.update({"status": "completed", "progress": 100,
                            "detail": "翻译完成", "outputs": message[1]})
                with self._lock:
                    self._translation_active = False
                self._emit("job-updated", job)
                self._notify("文档翻译完成", f"已生成 {Path(message[1][0]['path']).name}", "success")
                terminal = True
                break
            elif kind == "cancelled":
                job.update({"status": "cancelled", "detail": message[1]})
                with self._lock:
                    self._translation_active = False
                self._emit("job-updated", job)
                terminal = True
                break
            elif kind == "failed":
                job.update({"status": "failed", "detail": message[1]})
                with self._lock:
                    self._translation_active = False
                self._emit("job-updated", job)
                self._notify("翻译失败", message[1], "error")
                terminal = True
                break

        if not terminal:
            job = self._jobs[job_id]
            cancelled = self._cancel.is_set() or translation_cancel.is_set()
            job.update({"status": "cancelled" if cancelled else "failed",
                        "detail": "已取消" if cancelled else f"翻译进程意外退出（退出码 {process.exitcode}）"})
            with self._lock:
                self._translation_active = False
            self._emit("job-updated", job)
            if not cancelled:
                self._notify("翻译失败", job["detail"], "error")

    def cancel_translation(self) -> dict:
        self._cancel.set()
        if self._translation_cancel is not None:
            self._translation_cancel.set()
        return {"cancelled": True}

    def open_output(self, path: str = "") -> bool:
        target = Path(path) if path else self._output_dir
        if not path:
            target.mkdir(parents=True, exist_ok=True)
        if not target.resolve().is_relative_to(self._output_dir.resolve()) or not target.exists():
            raise ValueError("找不到输出文件。")
        os.startfile(target if target.is_dir() else target.parent)
        return True

    def choose_output_dir(self) -> dict:
        selected = self._create_file_dialog(webview.FOLDER_DIALOG)
        if selected:
            self._output_dir = Path(selected[0])
            self._settings["outputDir"] = str(self._output_dir)
            self._save_settings()
        return {"outputDir": str(self._output_dir)}

    def _emit(self, event: str, data: dict) -> None:
        if self._window:
            script = f"window.studioEvent({json.dumps(event)}, {json.dumps(data, ensure_ascii=False)})"

            # Bridge calls and jobs run on worker threads. pywebview marshals
            # evaluate_js internally; calling it through Invoke from here can
            # deadlock while the JavaScript API call is still awaiting a result.
            try:
                self._window.evaluate_js(script)
            except Exception:
                pass

    def _notify(self, title: str, message: str, kind: str) -> None:
        self._emit("notification", {"title": title, "message": message, "kind": kind})
