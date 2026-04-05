"""翻译 Worker 线程 — 支持分块、批量、取消"""

import os
import re
import time
import asyncio
import fitz  # PyMuPDF

from PyQt5.QtCore import QThread, pyqtSignal


# ─── 语言 / 服务映射 ─────────────────────────────────────────

LANG_MAP = {
    "自动检测": "", "English": "en", "日本語": "ja",
    "한국어": "ko", "Français": "fr", "Deutsch": "de",
    "中文(简体)": "zh", "中文(繁體)": "zh-TW",
    "Русский": "ru", "Español": "es", "Italiano": "it",
}

SERVICE_MAP = {
    "Bing 翻译": "bing",
    "Google 翻译": "google",
    "DeepL": "deepl",
    "DeepLX": "deeplx",
    "OpenAI": "openai",
    "Azure": "azure",
    "AzureOpenAI": "azure-openai",
    "Gemini": "gemini",
    "Ollama": "ollama",
    "Xinference": "xinference",
    "Zhipu (智谱)": "zhipu",
    "Tencent (腾讯)": "tencent",
    "DeepSeek": "deepseek",
    "Dify": "dify",
    "AnythingLLM": "anythingllm",
    "Argos Translate": "argos",
    "Groq": "groq",
    "Grok": "grok",
    "Silicon": "silicon",
    "Ali Qwen": "qwen-mt",
    "OpenAI-liked": "openai-liked",
}

PAGE_PRESETS = {
    "全部页面": None,
    "仅首页": [0],
    "前5页": list(range(0, 5)),
    "自定义": None,
}

OUTPUT_MODES = {
    "双语交替 (Dual)": "dual",
    "仅翻译 (Mono)": "mono",
    "左右并排 (Side by Side)": "side_by_side",
}


def detect_zotero_source(file_path: str):
    """检测文件是否来自 Zotero storage，返回 Zotero 子文件夹路径或 None

    匹配模式：
      .../Zotero/storage/XXXXXXXX/...
      .../zotero/storage/XXXXXXXX/...  (大小写不敏感)
    """
    m = re.search(r'[/\\][Zz]otero[/\\]storage[/\\][A-Za-z0-9]{8}[/\\]', file_path)
    if m:
        return file_path[:m.end()]
    return None


def get_zotero_item_key(file_path: str):
    """从 Zotero 路径提取 8 位 item key，如 'KSII2GGN'"""
    m = re.search(r'[/\\][Zz]otero[/\\]storage[/\\]([A-Za-z0-9]{8})[/\\]', file_path)
    return m.group(1) if m else None


def zotero_auto_link(item_key: str, file_path: str, title: str):
    """
    通过 pdf2zh-connector 插件将译文自动添加为 Zotero 附件。
    端点: POST http://127.0.0.1:23119/pdf2zh/attach
    返回 (success: bool, message: str)
    """
    import urllib.request
    import json
    payload = json.dumps({
        "itemKey": item_key,
        "filePath": file_path,
        "title": title,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:23119/pdf2zh/attach",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            if "error" in data:
                return False, data["error"]
            return True, f"已关联到 Zotero (key={data.get('key', '?')})"
    except urllib.error.URLError:
        return False, "pdf2zh Connector 未安装或 Zotero 未运行"
    except Exception as e:
        return False, str(e)


def zotero_plugin_installed():
    """检测 pdf2zh-connector 插件是否已安装"""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:23119/pdf2zh/ping")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_zotero_data_dir():
    """定位 Zotero 数据目录（含 zotero.sqlite）"""
    import platform
    candidates = [os.path.expanduser("~/Zotero")]
    if platform.system() == "Darwin":
        candidates.append(os.path.expanduser(
            "~/Library/Application Support/Zotero"))
    for d in candidates:
        if os.path.isfile(os.path.join(d, "zotero.sqlite")):
            return d
    return None


def resolve_zotero_items(item_ids):
    """从 Zotero SQLite 数据库把 itemID 列表解析为 PDF 文件路径列表。

    每个父条目只取最早的 PDF 附件（原始论文），跳过后来添加的翻译件。
    参数 item_ids: 数值型 item ID 列表（来自 zotero/item MIME）
    返回: PDF 绝对路径列表
    """
    import sqlite3
    data_dir = _find_zotero_data_dir()
    if not data_dir:
        return []
    db_path = os.path.join(data_dir, "zotero.sqlite")
    storage_dir = os.path.join(data_dir, "storage")
    pdfs = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(item_ids))
        # 1) item_ids 本身是 PDF 附件的情况
        cur.execute(
            f"SELECT i.key, ia.path FROM items i "
            f"JOIN itemAttachments ia ON i.itemID = ia.itemID "
            f"WHERE ia.contentType = 'application/pdf' "
            f"AND i.itemID IN ({placeholders})",
            item_ids,
        )
        for key, path in cur.fetchall():
            pdf = _resolve_zotero_path(storage_dir, key, path)
            if pdf:
                pdfs.append(pdf)
        # 2) item_ids 是父条目 → 只取每个父条目最早的 PDF 子附件
        #    ORDER BY ia.itemID 确保最早添加的排在前面
        cur.execute(
            f"SELECT ia.parentItemID, i.key, ia.path FROM items i "
            f"JOIN itemAttachments ia ON i.itemID = ia.itemID "
            f"WHERE ia.contentType = 'application/pdf' "
            f"AND ia.parentItemID IN ({placeholders}) "
            f"ORDER BY ia.itemID",
            item_ids,
        )
        seen_parents = set()
        for parent_id, key, path in cur.fetchall():
            if parent_id in seen_parents:
                continue  # 跳过同一父条目的后续附件（翻译件）
            pdf = _resolve_zotero_path(storage_dir, key, path)
            if pdf:
                pdfs.append(pdf)
                seen_parents.add(parent_id)
        conn.close()
    except Exception:
        pass
    # 去重保序
    seen = set()
    return [p for p in pdfs if not (p in seen or seen.add(p))]


def resolve_zotero_collection(collection_id_or_key):
    """从 Zotero SQLite 数据库把集合 ID 或 key 解析为 PDF 文件路径列表。

    参数: 数字型 collectionID 或 8 位 key（如 '7ZRBP23W'）
    返回: PDF 绝对路径列表
    """
    import sqlite3
    data_dir = _find_zotero_data_dir()
    if not data_dir:
        return []
    db_path = os.path.join(data_dir, "zotero.sqlite")
    storage_dir = os.path.join(data_dir, "storage")
    pdfs = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        cur = conn.cursor()
        # 支持 numeric ID 或 string key
        raw = str(collection_id_or_key).strip()
        if raw.isdigit():
            cur.execute(
                "SELECT collectionID FROM collections WHERE collectionID = ?",
                (int(raw),),
            )
        else:
            cur.execute(
                "SELECT collectionID FROM collections WHERE key = ?",
                (raw,),
            )
        row = cur.fetchone()
        if not row:
            conn.close()
            return []
        coll_id = row[0]
        # 集合里的父条目 → 每个只取最早的 PDF 附件
        cur.execute(
            "SELECT ia.parentItemID, i.key, ia.path FROM items i "
            "JOIN itemAttachments ia ON i.itemID = ia.itemID "
            "WHERE ia.contentType = 'application/pdf' "
            "AND ia.parentItemID IN "
            "(SELECT itemID FROM collectionItems WHERE collectionID = ?) "
            "ORDER BY ia.itemID",
            (coll_id,),
        )
        seen_parents = set()
        for parent_id, key, path in cur.fetchall():
            if parent_id in seen_parents:
                continue
            pdf = _resolve_zotero_path(storage_dir, key, path)
            if pdf:
                pdfs.append(pdf)
                seen_parents.add(parent_id)
        conn.close()
    except Exception:
        pass
    return pdfs


def _resolve_zotero_path(storage_dir, key, db_path):
    """把 Zotero 数据库中的 path 值解析为实际文件路径。

    Zotero path 格式: 'storage:filename.pdf'
    实际路径: {storage_dir}/{key}/{filename.pdf}
    """
    if not db_path:
        return None
    filename = db_path
    if filename.startswith("storage:"):
        filename = filename[len("storage:"):]
    full = os.path.join(storage_dir, key, filename)
    if os.path.isfile(full):
        return full
    return None


def resolve_zotero_by_title(text):
    """从 text/plain 中的标题文本匹配 Zotero 条目，返回对应 PDF 路径列表。

    macOS 跨进程拖拽时 Zotero 自定义 MIME 不可用，只能靠 text/plain。
    Zotero 拖拽条目时 text/plain 通常是引用文本，包含标题。
    """
    import sqlite3
    data_dir = _find_zotero_data_dir()
    if not data_dir:
        return []
    db_path = os.path.join(data_dir, "zotero.sqlite")
    storage_dir = os.path.join(data_dir, "storage")
    pdfs = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        cur = conn.cursor()
        # 每个父条目只取最早的 PDF 附件（原始论文）
        cur.execute(
            "SELECT ia.parentItemID, i.key, ia.path, ia.itemID "
            "FROM itemAttachments ia "
            "JOIN items i ON i.itemID = ia.itemID "
            "WHERE ia.contentType = 'application/pdf' "
            "AND ia.parentItemID IS NOT NULL "
            "ORDER BY ia.itemID"
        )
        parent_to_pdf = {}  # parentID → 第一个 PDF 路径
        for parent_id, key, path, _ in cur.fetchall():
            if parent_id in parent_to_pdf:
                continue
            pdf = _resolve_zotero_path(storage_dir, key, path)
            if pdf:
                parent_to_pdf[parent_id] = pdf
        if not parent_to_pdf:
            conn.close()
            return []
        # 查父条目的标题
        placeholders = ",".join("?" * len(parent_to_pdf))
        cur.execute(
            f"SELECT id.itemID, idv.value FROM itemData id "
            f"JOIN itemDataValues idv ON id.valueID = idv.valueID "
            f"WHERE id.fieldID IN (SELECT fieldID FROM fields WHERE fieldName='title') "
            f"AND id.itemID IN ({placeholders})",
            list(parent_to_pdf.keys()),
        )
        for item_id, title in cur.fetchall():
            # 标题长度 >= 8 才做子串匹配，避免 "4"、"AI" 等短标题误中
            if title and len(title) >= 8 and title in text:
                pdfs.append(parent_to_pdf[item_id])
        conn.close()
    except Exception:
        pass
    # 去重保序
    seen = set()
    return [p for p in pdfs if not (p in seen or seen.add(p))]


def resolve_zotero_collection_by_name(name):
    """通过集合名称匹配 Zotero 集合，返回其中所有 PDF 路径。

    macOS 跨进程拖拽时用：text/plain 可能包含集合名。
    """
    import sqlite3
    data_dir = _find_zotero_data_dir()
    if not data_dir:
        return []
    db_path = os.path.join(data_dir, "zotero.sqlite")
    storage_dir = os.path.join(data_dir, "storage")
    pdfs = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT collectionID FROM collections WHERE collectionName = ?",
            (name.strip(),),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return []
        coll_id = row[0]
        cur.execute(
            "SELECT ia.parentItemID, i.key, ia.path FROM items i "
            "JOIN itemAttachments ia ON i.itemID = ia.itemID "
            "WHERE ia.contentType = 'application/pdf' "
            "AND ia.parentItemID IN "
            "(SELECT itemID FROM collectionItems WHERE collectionID = ?) "
            "ORDER BY ia.itemID",
            (coll_id,),
        )
        seen_parents = set()
        for parent_id, key, path in cur.fetchall():
            if parent_id in seen_parents:
                continue
            pdf = _resolve_zotero_path(storage_dir, key, path)
            if pdf:
                pdfs.append(pdf)
                seen_parents.add(parent_id)
        conn.close()
    except Exception:
        pass
    return pdfs


def build_service_envs(svc_display_name):
    """从 GUI 配置构建翻译器 envs 字典

    将设置页保存的 api_/url_/model_ 前缀配置，映射为
    pdf2zh translator 所需的环境变量名（如 DEEPSEEK_API_KEY）。
    """
    from ui.config_manager import UserConfigManager

    # 翻译页显示名 → (设置页配置前缀, {gui字段: translator环境变量名})
    _MAP = {
        "OpenAI":          ("OpenAI",           {"api": "OPENAI_API_KEY",       "url": "OPENAI_BASE_URL",       "model": "OPENAI_MODEL"}),
        "AzureOpenAI":     ("Azure OpenAI",     {"api": "AZURE_OPENAI_API_KEY", "url": "AZURE_OPENAI_BASE_URL", "model": "AZURE_OPENAI_MODEL"}),
        "DeepL":           ("DeepL",            {"api": "DEEPL_AUTH_KEY"}),
        "Gemini":          ("Gemini",           {"api": "GEMINI_API_KEY",       "url": "GEMINI_BASE_URL",       "model": "GEMINI_MODEL"}),
        "Groq":            ("Groq",             {"api": "GROQ_API_KEY",         "url": "GROQ_BASE_URL",         "model": "GROQ_MODEL"}),
        "DeepSeek":        ("DeepSeek",         {"api": "DEEPSEEK_API_KEY",     "url": "DEEPSEEK_BASE_URL",     "model": "DEEPSEEK_MODEL"}),
        "Zhipu (智谱)":   ("Zhipu 智谱",      {"api": "ZHIPU_API_KEY",        "url": "ZHIPU_BASE_URL",        "model": "ZHIPU_MODEL"}),
        "Tencent (腾讯)": ("Tencent 腾讯",     {"api": "TENCENTCLOUD_SECRET_ID"}),
        "Silicon":         ("Silicon 硅基流动", {"api": "SILICON_API_KEY",      "url": "SILICON_BASE_URL",      "model": "SILICON_MODEL"}),
        "Ollama":          ("Ollama 本地",      {"model": "OLLAMA_MODEL"}),
        "AnythingLLM":     ("AnythingLLM",      {"api": "AnythingLLM_APIKEY",   "url": "AnythingLLM_URL"}),
        "Grok":            ("Grok",             {"api": "GORK_API_KEY",         "url": "GORK_BASE_URL",         "model": "GORK_MODEL"}),
        "OpenAI-liked":    ("OpenAI 兼容",     {"api": "OPENAILIKED_API_KEY",  "url": "OPENAILIKED_BASE_URL",  "model": "OPENAILIKED_MODEL"}),
    }

    mapping = _MAP.get(svc_display_name)
    if not mapping:
        return {}

    cfg_prefix, env_keys = mapping
    cfg = UserConfigManager.load()
    envs = {}

    for field, env_key in env_keys.items():
        if field == "api":
            raw = cfg.get(f"api_{cfg_prefix}", "")
            val = UserConfigManager.decode_sensitive(raw) if raw else ""
        elif field == "model":
            val = cfg.get(f"model_{cfg_prefix}", "")
        elif field == "url":
            val = cfg.get(f"url_{cfg_prefix}", "")
        else:
            continue
        if val:
            envs[env_key] = val

    return envs


def parse_page_range(text: str):
    """解析页码范围字符串，如 '1-5, 8, 10-12'，返回 0-indexed list"""
    pages = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start.strip()) - 1, int(end.strip())))
        else:
            pages.append(int(part) - 1)
    return sorted(set(p for p in pages if p >= 0))


def create_side_by_side_pdf(mono_path: str, dual_path: str, output_path: str):
    """
    从 dual PDF 生成左右并排 PDF:
    左边 = 原文页（dual 偶数页），右边 = 译文页（dual 奇数页）
    """
    doc_dual = fitz.open(dual_path)
    doc_out = fitz.open()

    # dual 格式: page 0 = 原文第1页, page 1 = 译文第1页, page 2 = 原文第2页, ...
    num_pairs = len(doc_dual) // 2

    for i in range(num_pairs):
        orig_page = doc_dual[i * 2]
        trans_page = doc_dual[i * 2 + 1]

        orig_rect = orig_page.rect
        trans_rect = trans_page.rect

        new_w = orig_rect.width + trans_rect.width
        new_h = max(orig_rect.height, trans_rect.height)

        new_page = doc_out.new_page(width=new_w, height=new_h)

        # 左边放原文
        new_page.show_pdf_page(
            fitz.Rect(0, 0, orig_rect.width, new_h),
            doc_dual, i * 2
        )
        # 右边放译文
        new_page.show_pdf_page(
            fitz.Rect(orig_rect.width, 0, new_w, new_h),
            doc_dual, i * 2 + 1
        )
        # 中间分割线
        new_page.draw_line(
            fitz.Point(orig_rect.width, 0),
            fitz.Point(orig_rect.width, new_h),
            color=(0.7, 0.7, 0.7),
            width=0.8,
        )

    doc_out.save(output_path, deflate=True, garbage=3)
    doc_dual.close()
    doc_out.close()
    return output_path


class TranslateWorker(QThread):
    """单文件翻译 Worker — 支持分块"""

    progress = pyqtSignal(int, int)       # current_page, total_pages
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)           # {"mono": path, "dual": path, "side_by_side": path}
    error = pyqtSignal(str)

    def __init__(self, file_path, output_dir, lang_in, lang_out, service,
                 pages=None, thread_count=8, chunk_enabled=False,
                 chunk_size=50, chunk_delay=10, envs=None,
                 skip_subset_fonts=False, ignore_cache=False,
                 parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.output_dir = output_dir
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.service = service
        self.pages = pages
        self.thread_count = thread_count
        self.chunk_enabled = chunk_enabled
        self.chunk_size = chunk_size
        self.chunk_delay = chunk_delay
        self.envs = envs
        self.skip_subset_fonts = skip_subset_fonts
        self.ignore_cache = ignore_cache
        self.cancelled = False
        self._cancel_event = None

    # 需要 API Key 的服务列表
    SERVICES_NEED_KEY = {
        "deepseek", "openai", "azure", "azure-openai", "deepl", "deeplx",
        "gemini", "zhipu", "tencent", "dify", "anythingllm", "groq", "grok",
        "silicon", "qwen-mt", "openai-liked",
    }

    def run(self):
        try:
            from pdf2zh import translate
            from pdf2zh.doclayout import OnnxModel
        except ImportError as e:
            self.error.emit(f"模块加载失败: {e}")
            return

        # API Key 预检查
        if self.service in self.SERVICES_NEED_KEY:
            from ui.config_manager import UserConfigManager
            cfg = UserConfigManager.load()
            has_key = False
            for k, v in cfg.items():
                if k.startswith("api_") and v:
                    has_key = True
                    break
            # 同时检查环境变量
            import os as _os
            for env_name in ["OPENAI_API_KEY", "DEEPL_AUTH_KEY", "DEEPSEEK_API_KEY"]:
                if _os.environ.get(env_name):
                    has_key = True
            if not has_key:
                self.error.emit(
                    f"「{self.service}」需要 API Key。\n"
                    f"请在「设置 → 翻译服务密钥」中填写，或使用免费服务（Bing/Google）。"
                )
                return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            self.status.emit("正在加载 AI 布局模型…")
            # 优先用打包内的模型文件
            import sys
            bundled_model = os.path.join(
                getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(__file__))),
                'assets', 'doclayout_yolo.onnx'
            )
            if os.path.exists(bundled_model):
                model = OnnxModel(bundled_model)
            else:
                model = OnnxModel.load_available()
            self._cancel_event = asyncio.Event()

            # 获取总页数
            doc = fitz.open(self.file_path)
            total_pages = len(doc)
            doc.close()

            # 翻译参数基础模板（和原版一致）
            base_param = dict(
                files=[self.file_path],
                output=self.output_dir,
                lang_in=self.lang_in,
                lang_out=self.lang_out,
                service=self.service,
                thread=self.thread_count,
                model=model,
                cancellation_event=self._cancel_event,
                envs=self.envs or {},
            )

            def on_progress(p):
                try:
                    c = getattr(p, 'n', 0) or 0
                    t = getattr(p, 'total', 0) or 0
                    if t > 0:
                        self.progress.emit(int(c), int(t))
                except Exception:
                    pass

            # ══════════════════════════════════════════
            #  分块翻译（和原版 AaronGIG 逻辑一致）
            #  条件：开启分块 AND 翻译全部页面（无自定义页码）
            # ══════════════════════════════════════════
            if self.chunk_enabled and self.pages is None:
                num_chunks = (total_pages + self.chunk_size - 1) // self.chunk_size
                self.status.emit(
                    f"分块翻译: {total_pages} 页 → {num_chunks} 块 "
                    f"(每块 {self.chunk_size} 页, 间隔 {self.chunk_delay}s)"
                )

                for chunk_idx in range(num_chunks):
                    if self.cancelled:
                        self.error.emit("已取消")
                        return

                    start_page = chunk_idx * self.chunk_size
                    end_page = min(start_page + self.chunk_size, total_pages)
                    chunk_pages = list(range(start_page, end_page))

                    self.status.emit(
                        f"第 {chunk_idx+1}/{num_chunks} 块 "
                        f"(第 {start_page+1}-{end_page} 页)…"
                    )

                    base_param["pages"] = chunk_pages
                    base_param["callback"] = on_progress
                    translate(**base_param)

                    # 块间延迟（防限流 — 和原版一致，逐秒倒计时）
                    if self.chunk_delay > 0 and chunk_idx < num_chunks - 1 and not self.cancelled:
                        for sec in range(self.chunk_delay, 0, -1):
                            if self.cancelled:
                                break
                            self.status.emit(f"暂停 {sec} 秒，避免限流…")
                            time.sleep(1)

                # 最终合成：pages=None，利用缓存，速度很快
                self.status.emit("正在利用缓存合成完整文件…")
                base_param["pages"] = None
                base_param["callback"] = on_progress
                results = translate(**base_param)

            # ══════════════════════════════════════════
            #  直接翻译（无分块 或 自定义页码）
            # ══════════════════════════════════════════
            else:
                self.status.emit("正在翻译…")
                base_param["pages"] = self.pages  # None = 全部, list = 指定
                base_param["callback"] = on_progress
                results = translate(**base_param)

            if self.cancelled:
                self.error.emit("已取消")
                return

            result_list = list(results)
            if not result_list:
                self.error.emit("翻译返回空结果")
                return

            mono_path, dual_path = result_list[0]

            # ── 生成 Side-by-Side ──
            self.status.emit("正在生成左右并排版…")
            base = os.path.splitext(mono_path)[0]
            if base.endswith("-mono"):
                base = base[:-5]
            sbs_path = base + "-side_by_side.pdf"

            try:
                create_side_by_side_pdf(mono_path, dual_path, sbs_path)
            except Exception as e:
                sbs_path = ""
                self.status.emit(f"并排版生成失败: {e}")

            self.status.emit("翻译完成")
            self.finished.emit({
                "mono": mono_path,
                "dual": dual_path,
                "side_by_side": sbs_path,
            })

        except KeyError as e:
            self.error.emit(f"缺少 API Key: {e}。请在「设置」中填写对应服务的密钥。")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # 取最后一行有意义的错误信息
            msg = str(e) or tb.strip().split('\n')[-1]
            self.error.emit(msg)
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def cancel(self):
        self.cancelled = True
        if self._cancel_event:
            self._cancel_event.set()
