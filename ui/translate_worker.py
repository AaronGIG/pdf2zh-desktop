"""翻译 Worker 线程 — 支持分块、批量、取消"""

import os
import re
import time
import asyncio
import fitz  # PyMuPDF

from PyQt5.QtCore import QThread, pyqtSignal


def _table_cell_fit_fontsize(w, h, text, max_fontsize=12, min_fontsize=6):
    """基于单元格面积估算最佳字号，让 insert_textbox 自动换行贴近原版排版密度。
    和 core/site-packages/pdf2zh/high_level.py 的 _fit_fontsize 逻辑一致——之前 Mac
    端只按格子高度算字号（不管译文有多长），中文比英文原文平均更长，经常挤成
    密密麻麻好几行换行，看起来比原版乱很多。
    v2.3.14: 参数从 rect 改成显式 w/h——竖排/旋转的单元格用 insert_textbox 的
    rotate= 参数插入时，文字实际的"流动宽度"对应的是 rect 的高，不是宽，
    调用方需要按旋转角度自己决定传谁当 w、谁当 h。"""
    if w <= 0 or h <= 0:
        return min_fontsize
    cjk = sum(1 for c in text if ord(c) > 0x2fff)
    latin = len(text) - cjk
    for size in [max_fontsize, 12, 11, 10, 9, 8, 7, min_fontsize]:
        char_w_cjk = size * 1.0
        char_w_latin = size * 0.52
        line_height = size * 1.3
        text_total_w = cjk * char_w_cjk + latin * char_w_latin
        lines = max(1, text_total_w / w)
        needed_h = lines * line_height
        if needed_h <= h + size * 0.5:
            return size
    return min_fontsize


def _table_cell_should_translate(text: str) -> bool:
    """判断表格单元格文字是否需要翻译（跳过纯数字/日期/编号/单字符），
    和 core/site-packages/pdf2zh/high_level.py 里 Win 端的 _should_translate 逻辑一致。
    没有这层过滤时纯数字单元格（如 "893"）会被送进翻译服务，偶尔被曲解成
    "第893章"这类无意义结果。
    v2.3.14: 学术表格里统计区间/置信区间常见写法（如 "87.2 (81.8–91.2)"）用的是
    半字线 – 而不是普通连字符 -，加上括号，原来的正则接不住，被当成"需要翻译"
    送进 Google 翻译——数字部分翻译器不会真的翻，但经常会顺手把换行/空格重新
    排版一下（比如去掉数字和括号之间的换行），导致 translated != 原文本，
    又触发白底覆盖+重新插入，新插入的文字用了不同的自动换行方式，和相邻单元格
    的内容挤在一起变成乱码堆。把这类"纯统计数值+区间符号"也一并识别成不需要
    翻译，从根上避免这次没意义的覆盖重排。"""
    if not text or not text.strip():
        return False
    t = text.strip()
    if len(t) <= 1:
        return False
    if re.match(r'^[+\-–—±()\[\]~\d.,\s%/:\-]+$', t):
        return False
    return True


def _table_cell_rotation_and_size(page, rect):
    """判断表格单元格里的文字排版方向 + 原始字号，一次 get_text 扫描顺带都拿到。
    返回 (rotate, ref_size) 或 (None, None)（拿不到可靠方向/字号，或同一格里混了
    不同方向时——大概率是 find_tables 格子边界不准，交给调用方跳过不处理）。
    ref_size 用原文里出现过的最大字号，插入译文时以它封顶——之前每个格子完全
    独立按译文长度反推字号，同一张表里长短不一的译文算出来的字号差异很大，
    看起来东一块大字西一块小字，比原表格乱很多；原表格本身字号通常是统一的，
    直接拿原字号当上限更接近原版观感。
    v2.3.14 (issue #28 后续): 论文里常见整张表格转 90° 排版（不只是列标题旋转，
    数据单元格本身也是转向的——之前只验证过标题行旋转，误以为数据格是水平的）。
    这类表格如果不加区分地把提取到的文字横排插入回去，会跟原有竖排内容方向不一致、
    版式全乱。这里用 PyMuPDF 提取到的文字行方向向量 dir 判断朝向，再插入时按同样
    角度旋转译文，保持和原表格一致的排版方向，而不是简单跳过整张表不翻译。
    dir≈(±1,0) 水平；dir≈(0,-1)（PyMuPDF 图像坐标系，文字从下往上走）对应
    insert_textbox 的 rotate=90；dir≈(0,1) 对应 rotate=270。
    v2.3.14 修正：第一版按"整句顺序读出来对不对"判断，结果和 270 判反了——
    对中文这种每个字本身方向对称的文字，顺序读得通不代表每个字"正立"方向对，
    实测拿原表格里未改动的英文原文字符(如"Model"/"IDx-DR")逐字对比朝向才发现
    刚好反了，插入译文单个字都是倒着立的，和原表格其他没被覆盖的旋转内容缺一撞就
    出现"有的顺时针有的逆时针"的观感。
    """
    d = page.get_text("dict", clip=rect)
    dirs = set()
    max_size = 0
    for blk in d.get("blocks", []):
        for ln in blk.get("lines", []):
            dx, dy = ln.get("dir", (1.0, 0.0))
            if abs(dx) >= abs(dy):
                dirs.add(180 if dx < 0 else 0)
            else:
                dirs.add(90 if dy < 0 else 270)
            for sp in ln.get("spans", []):
                max_size = max(max_size, sp.get("size", 0))
    if len(dirs) != 1 or max_size <= 0:
        return None, None  # 没有文字，或者同一格里混了不止一种方向(大概率是 find_tables 格子边界不准)，不处理
    return dirs.pop(), max_size


def _table_cell_texts_equivalent(a: str, b: str) -> bool:
    """判断两段单元格文字是否"实质等价"（忽略空白/换行/破折号变体差异）。
    v2.3.14: 翻译服务经常对数字/符号为主的文本做无意义的格式重排（换行变空格、
    半字线变连字符等），如果只用严格字符串相等判断"是否需要重新插入"，会把这类
    格式抖动误判成"有实质变化"，导致没必要的白底覆盖+插入，反而和相邻单元格内容
    叠在一起。"""
    def _norm(s):
        s = re.sub(r'\s+', '', s.strip())  # 判等用途，直接去掉全部空白差异（不只是压缩）
        for dash in ('–', '—', '‐', '‑'):
            s = s.replace(dash, '-')
        return s
    return _norm(a) == _norm(b)


# ─── 语言 / 服务映射 ─────────────────────────────────────────

LANG_MAP = {
    "自动检测": "", "English": "en", "日本語": "ja",
    "한국어": "ko", "Français": "fr", "Deutsch": "de",
    "中文(简体)": "zh", "中文(繁體)": "zh-TW",
    "Русский": "ru", "Español": "es", "Italiano": "it",
}

SERVICE_MAP = {
    "Google 翻译": "google",
    "Bing 翻译": "bing",
    "DeepSeek": "deepseek",
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
    "Dify": "dify",
    "AnythingLLM": "anythingllm",
    # Argos Translate 因离线包依赖（ctranslate2 等）过大未集成，桌面版不开放此服务
    # "Argos Translate": "argos",
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


def _local_opener():
    """v2.3.2: 到 127.0.0.1 / localhost 的请求必须绕过系统 HTTP 代理
    (clash/v2ray/学术代理 等会把 loopback 请求转到外网返回 502 Bad Gateway)
    """
    import urllib.request
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def zotero_auto_link(item_key: str, file_path: str, title: str):
    """
    通过 pdf2zh-connector 插件将译文自动添加为 Zotero 附件。
    端点: POST http://127.0.0.1:23119/pdf2zh/attach
    返回 (success: bool, message: str)
    """
    import urllib.request
    import urllib.error
    import unicodedata
    import json
    # macOS 文件系统用 NFD，Python 默认 NFC，混用会导致 Zotero 找不到文件
    normalized_path = unicodedata.normalize('NFC', os.path.abspath(file_path))
    payload = json.dumps({
        "itemKey": item_key,
        "filePath": normalized_path,
        "title": title,
    }, ensure_ascii=False).encode("utf-8")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:23119/pdf2zh/attach",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _local_opener().open(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            if "error" in data:
                return False, f"Zotero 插件报错：{data['error']}"
            return True, (f"✅ 已同步到 Zotero(key={data.get('key','?')})"
                          " → 打开 Zotero 看原文献下的『Translated PDF』附件")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "❌ Zotero 联动失败：插件未装或未启用 → 请下载最新 xpi 手动装"
        if e.code == 502:
            return False, "❌ Zotero 联动失败：HTTP 502 (代理拦截了 loopback 请求；已修，请重启 pdf2zh)"
        return False, f"❌ Zotero 联动失败：HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, "❌ Zotero 联动失败：Zotero 未打开 → 请打开 Zotero 后重新翻译"
    except Exception as e:
        return False, f"❌ Zotero 联动失败：{str(e)[:120]}"


def zotero_plugin_installed():
    """检测 pdf2zh-connector 插件是否已安装"""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:23119/pdf2zh/ping")
        # v2.3.2: 绕过系统代理
        with _local_opener().open(req, timeout=3) as resp:
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
        "Azure":           ("Azure",            {"api": "AZURE_API_KEY",        "url": "AZURE_ENDPOINT"}),
        "AzureOpenAI":     ("Azure OpenAI",     {"api": "AZURE_OPENAI_API_KEY", "url": "AZURE_OPENAI_BASE_URL", "model": "AZURE_OPENAI_MODEL"}),
        "DeepL":           ("DeepL",            {"api": "DEEPL_AUTH_KEY"}),
        "Gemini":          ("Gemini",           {"api": "GEMINI_API_KEY",       "url": "GEMINI_BASE_URL",       "model": "GEMINI_MODEL"}),
        "Groq":            ("Groq",             {"api": "GROQ_API_KEY",         "url": "GROQ_BASE_URL",         "model": "GROQ_MODEL"}),
        "DeepSeek":        ("DeepSeek",         {"api": "DEEPSEEK_API_KEY",     "url": "DEEPSEEK_BASE_URL",     "model": "DEEPSEEK_MODEL"}),
        "Zhipu (智谱)":   ("Zhipu 智谱",      {"api": "ZHIPU_API_KEY",        "url": "ZHIPU_BASE_URL",        "model": "ZHIPU_MODEL"}),
        "Tencent (腾讯)": ("Tencent 腾讯",     {"api": "TENCENTCLOUD_SECRET_ID"}),
        "Dify":            ("Dify",             {"api": "DIFY_API_KEY",         "url": "DIFY_API_URL"}),
        "Silicon":         ("Silicon 硅基流动", {"api": "SILICON_API_KEY",      "url": "SILICON_BASE_URL",      "model": "SILICON_MODEL"}),
        "Ollama":          ("Ollama 本地",      {"model": "OLLAMA_MODEL"}),
        "AnythingLLM":     ("AnythingLLM",      {"api": "AnythingLLM_APIKEY",   "url": "AnythingLLM_URL"}),
        "Grok":            ("Grok",             {"api": "GORK_API_KEY",         "url": "GORK_BASE_URL",         "model": "GORK_MODEL"}),
        "Ali Qwen":        ("Qwen 通义千问",   {"api": "OPENAI_API_KEY",       "url": "OPENAI_BASE_URL",       "model": "OPENAI_MODEL"}),
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
                 scan_mode=False, translate_tables=False, table_pages=None, ocr_mode=False,
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
        self.scan_mode = scan_mode
        self.translate_tables = translate_tables
        self.table_pages = table_pages
        self.ocr_mode = ocr_mode
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

        # API Key 预检查（修复 issue #16: 精确检查当前 service 对应的 key 字段）
        if self.service in self.SERVICES_NEED_KEY:
            envs_for_check = self.envs or {}
            # service 名 → API Key 环境变量名
            _SVC_TO_ENV = {
                "deepseek": "DEEPSEEK_API_KEY",
                "openai": "OPENAI_API_KEY",
                "azure": "AZURE_API_KEY",
                "azure-openai": "AZURE_OPENAI_API_KEY",
                "deepl": "DEEPL_AUTH_KEY",
                "deeplx": "DEEPLX_AUTH_KEY",
                "gemini": "GEMINI_API_KEY",
                "zhipu": "ZHIPU_API_KEY",
                "tencent": "TENCENTCLOUD_SECRET_ID",
                "dify": "DIFY_API_KEY",
                "anythingllm": "AnythingLLM_APIKEY",
                "groq": "GROQ_API_KEY",
                "grok": "GORK_API_KEY",
                "silicon": "SILICON_API_KEY",
                "qwen-mt": "OPENAI_API_KEY",
                "openai-liked": "OPENAILIKED_API_KEY",
            }
            need_env = _SVC_TO_ENV.get(self.service)
            import os as _os
            has_key = bool(envs_for_check.get(need_env)) if need_env else False
            if not has_key and need_env:
                # 兜底：环境变量
                has_key = bool(_os.environ.get(need_env))
            if not has_key:
                self.error.emit(
                    f"「{self.service}」的 API Key 未配置。\n\n"
                    f"请进入「设置」页，找到对应服务（如 DeepSeek）填入密钥，"
                    f"然后**点击输入框外任意位置**或按 Tab，确保保存生效。\n\n"
                    f"如已填写仍报错：检查 ~/.config/pdf2zh/config.json 里 "
                    f"api_<服务名> 字段是否为空。"
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

            # 预处理链
            actual_file = self.file_path

            # OCR 预处理：纯图片扫描件 → 添加不可见文字层
            if self.ocr_mode:
                self.status.emit("正在 OCR 识别…")
                actual_file = self._ocr_preprocess(actual_file)

            # 翻译参数基础模板（pdf2zh 1.8.9 兼容）
            base_param = dict(
                files=[actual_file],
                output=self.output_dir,
                lang_in=self.lang_in,
                lang_out=self.lang_out,
                service=self.service,
                thread=self.thread_count,
                model=model,
                cancellation_event=self._cancel_event,
                envs=self.envs or {},
                scan_mode=self.scan_mode,
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

            # ── 表格翻译后处理 ──
            table_translate_result = None
            if self.translate_tables:
                self.status.emit("正在翻译表格内容…")
                for pdf_path in [mono_path, dual_path]:
                    if pdf_path and os.path.exists(pdf_path):
                        r = self._translate_tables_postprocess(pdf_path)
                        # mono/dual 各跑一次，取"更有信息量"的结果（累计翻译数，取最后一次报错）
                        if table_translate_result is None:
                            table_translate_result = r
                        else:
                            table_translate_result["tables_found"] += r.get("tables_found", 0)
                            table_translate_result["cells_translated"] += r.get("cells_translated", 0)
                            if r.get("error"):
                                table_translate_result["error"] = r["error"]

            # ── 生成 Side-by-Side（可选：output_formats 控制是否生成）──
            base = os.path.splitext(mono_path)[0]
            if base.endswith("-mono"):
                base = base[:-5]
            sbs_path = base + "-side_by_side.pdf"

            # v2.3.0：output_formats 控制只输出用户要的格式（默认全出保持兼容）
            output_formats = getattr(self, "output_formats", None) or ["mono", "dual", "side_by_side"]
            need_sbs = "side_by_side" in output_formats

            if need_sbs:
                self.status.emit("正在生成左右并排版…")
                try:
                    create_side_by_side_pdf(mono_path, dual_path, sbs_path)
                except Exception as e:
                    sbs_path = ""
                    self.status.emit(f"并排版生成失败: {e}")
            else:
                sbs_path = ""

            # 删掉用户不要的中间文件（比如只要 side_by_side 时删 mono/dual）
            try:
                if "mono" not in output_formats and mono_path and os.path.exists(mono_path):
                    os.remove(mono_path); mono_path = ""
                if "dual" not in output_formats and dual_path and os.path.exists(dual_path):
                    os.remove(dual_path); dual_path = ""
            except Exception:
                pass

            self.status.emit("翻译完成")
            self.finished.emit({
                "mono": mono_path,
                "dual": dual_path,
                "side_by_side": sbs_path,
                "table_translate_result": table_translate_result,
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
            # 清理 OCR 预处理产生的临时文件
            if actual_file != self.file_path and os.path.exists(actual_file):
                try:
                    os.remove(actual_file)
                except OSError:
                    pass

    # ── OCR 预处理：纯图片扫描件添加不可见文字层 ──

    def _ocr_preprocess(self, file_path):
        """对纯图片 PDF 先 OCR 识别，添加文字层后返回临时文件路径"""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            self.status.emit("OCR 模块未安装，跳过")
            return file_path

        doc = None
        try:
            ocr = RapidOCR()
            doc = fitz.open(file_path)
            modified = False

            for page_num in range(doc.page_count):
                if self.cancelled:
                    break
                page = doc[page_num]
                if page.get_text().strip():
                    continue  # 已有文字层，跳过

                pix = page.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                result, _ = ocr(img_data)
                if not result:
                    continue

                scale_x = page.rect.width / pix.width
                scale_y = page.rect.height / pix.height
                for line in result:
                    box, text, confidence = line
                    if confidence < 0.5:
                        continue
                    x0 = min(p[0] for p in box) * scale_x
                    y0 = min(p[1] for p in box) * scale_y
                    x1 = max(p[0] for p in box) * scale_x
                    y1 = max(p[1] for p in box) * scale_y
                    font_size = max((y1 - y0) * 0.8, 4)
                    rc = fitz.Rect(x0, y0, x1, y1)
                    page.insert_textbox(
                        rc, text, fontsize=font_size,
                        fontname="helv", color=(0, 0, 0),
                        render_mode=3,  # 3 = invisible
                    )
                    modified = True
                self.status.emit(f"OCR 识别中… {page_num+1}/{doc.page_count}")

            if modified:
                import tempfile
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                doc.save(tmp.name)
                doc.close()
                doc = None
                return tmp.name
        except Exception as e:
            self.status.emit(f"OCR 失败: {e}")
        finally:
            if doc:
                try: doc.close()
                except Exception: pass
        return file_path

    # ── 表格翻译后处理 ──

    def _get_table_translator(self):
        """构造和正文翻译同一个服务的翻译器实例。
        v2.3.11 修复：这里原来固定调用 ui/ai_client.py 的 chat_completion，
        那是一套独立的"AI 助手"配置（在设置里单独填 DeepSeek/OpenAI 等 key），
        和用户在主界面选的翻译服务（哪怕选的是完全不需要 key 的 Google/Bing）
        是两码事。用户只配了正文用的翻译服务、没额外配 AI 助手 key 时，
        chat_completion 每个单元格都会抛 RuntimeError，又被下面的
        `except: pass` 悄悄吞掉——界面上看起来就是"勾了表格翻译但表格纹丝不动，
        也不报错"。改成直接复用正文那个服务/model/envs 构造同一个 translator
        实例，和正文用的是同一套翻译能力，不再依赖额外配置。
        """
        import pdf2zh.translator as _t
        # 用 getattr 逐个取，不用一次性 from...import：不同版本 pdf2zh 打包进来的
        # translator 类集合不完全一样（比如老版本类名是 GorkTranslator 不是
        # GrokTranslator、没有 QwenMtTranslator），整体 import 一个都不存在就
        # 全部失败；这里缺哪个就跳过哪个，用 .name 属性匹配用户选的服务标识符
        # （和类名拼写无关）。
        candidate_names = [
            "GoogleTranslator", "BingTranslator", "DeepLTranslator", "DeepLXTranslator",
            "OllamaTranslator", "XinferenceTranslator", "AzureOpenAITranslator",
            "OpenAITranslator", "ZhipuTranslator", "ModelScopeTranslator",
            "SiliconTranslator", "GeminiTranslator", "AzureTranslator",
            "TencentTranslator", "DifyTranslator", "AnythingLLMTranslator",
            "ArgosTranslator", "GrokTranslator", "GorkTranslator", "GroqTranslator",
            "DeepseekTranslator", "OpenAIlikedTranslator", "QwenMtTranslator",
        ]
        param = (self.service or "").split(":", 1)
        service_name = param[0]
        service_model = param[1] if len(param) > 1 else None
        for cls_name in candidate_names:
            translator_cls = getattr(_t, cls_name, None)
            if translator_cls is None:
                continue
            if service_name == getattr(translator_cls, "name", None):
                return translator_cls(self.lang_in, self.lang_out, service_model,
                                       envs=self.envs or {}, ignore_cache=False)
        raise RuntimeError(f"未识别的翻译服务: {self.service}")

    def _translate_tables_postprocess(self, pdf_path):
        """提取表格文字，翻译后写回（独立管线，不影响正文排版）。
        v2.3.13: 之前不管成功还是失败都只往 self.status（transient 的进度条文案，
        马上会被"翻译完成"等后续状态覆盖掉）发一条消息，用户基本看不到。这里
        改成返回一个诊断结果 dict（表格数/翻译成功数/最后一次报错），交给调用方
        （run() -> finished 信号）带出去，在主界面用持久提示展示，而不是转瞬即逝
        的状态栏文字——这正是 v2.3.11 那个"勾了但悄无声息失败"问题的同款根因，
        这次把"看不见"这一层也一起堵上，不管以后是什么新原因导致翻译失败，
        用户都能看到具体报错，而不是又一次"什么都没发生"。
        返回: {"tables_found": int, "cells_translated": int, "error": str|None}
        """
        result = {"tables_found": 0, "cells_translated": 0, "error": None}
        try:
            translator = self._get_table_translator()
        except Exception as e:
            result["error"] = str(e)
            self.status.emit(f"表格翻译跳过（{e}）")
            return result
        last_cell_error = None
        try:
            doc = fitz.open(pdf_path)
            # v2.3.11: 表格后处理原来永远扫全篇，不管主翻译有没有限定页码范围
            # （self.pages）。改成同步遵守同一个页码限制。
            # v2.3.12: 支持表格翻译单独指定页码（self.table_pages）——常见需求是
            # "正文整篇正常翻译，只想对某几页的表格做单元格翻译"，这时主翻译的
            # self.pages 是 None（全篇），但用户只想让表格翻译跑在指定的几页上。
            # 优先级：table_pages（表格专用页码）> pages（主翻译页码范围）> 全篇。
            effective_pages = self.table_pages if self.table_pages else self.pages
            page_range = range(doc.page_count) if not effective_pages else [p for p in effective_pages if 0 <= p < doc.page_count]
            for page_num in page_range:
                if self.cancelled:
                    break
                page = doc[page_num]
                tables = page.find_tables()
                if not tables or not tables.tables:
                    continue
                result["tables_found"] += len(tables.tables)
                for table in tables.tables:
                    for cell in table.cells:
                        if cell is None:
                            continue
                        rect = fitz.Rect(cell)
                        text = page.get_textbox(rect).strip()
                        if not _table_cell_should_translate(text):
                            continue
                        rot, ref_size = _table_cell_rotation_and_size(page, rect)
                        if rot is None:
                            continue  # 方向不明或一格里混了多种方向(find_tables 边界不准)，跳过更安全
                        # 翻译单元格文字
                        try:
                            translated = translator.translate(text)
                            if translated and translated.strip() and not _table_cell_texts_equivalent(translated, text):
                                # 白底覆盖 + 写入译文（按原方向旋转插入，保持和周围表格一致的排版方向）
                                shape = page.new_shape()
                                shape.draw_rect(rect)
                                shape.finish(color=None, fill=(1, 1, 1))
                                shape.commit()
                                translated_text = translated.strip()
                                # v2.3.14: 旋转 90/270 插入时，文字实际沿着 rect 的高在走，
                                # 而不是宽——算字号要把 w/h 对调，否则窄长的竖排格子会按
                                # "又宽又矮"估出偏大的字号，插入时严重溢出到相邻格子。
                                fit_w, fit_h = (rect.width, rect.height) if rot in (0, 180) else (rect.height, rect.width)
                                # 用原文字号封顶，避免同一张表里长短不一的译文算出差异很大的字号
                                max_fs = min(12, max(ref_size, 6))
                                font_size = _table_cell_fit_fontsize(fit_w - 2, fit_h - 2, translated_text, max_fontsize=max_fs)
                                rc = page.insert_textbox(
                                    rect, translated_text,
                                    fontsize=font_size, fontname="china-s",
                                    color=(0, 0, 0), align=fitz.TEXT_ALIGN_LEFT, rotate=rot,
                                )
                                if rc < 0 and font_size > 6:
                                    # 仍然放不下（估算和实际渲染有偏差），最小字号兜底重试一次
                                    shape = page.new_shape()
                                    shape.draw_rect(rect)
                                    shape.finish(color=None, fill=(1, 1, 1))
                                    shape.commit()
                                    page.insert_textbox(
                                        rect, translated_text,
                                        fontsize=6, fontname="china-s",
                                        color=(0, 0, 0), align=fitz.TEXT_ALIGN_LEFT, rotate=rot,
                                    )
                                result["cells_translated"] += 1
                        except Exception as e:
                            last_cell_error = str(e)  # 单个单元格失败不影响其他，但记下最后一次报错
                self.status.emit(f"表格翻译… {page_num+1}/{doc.page_count}")
            doc.saveIncr()
            doc.close()
        except Exception as e:
            result["error"] = str(e)
            return result
        if result["cells_translated"] == 0 and last_cell_error:
            result["error"] = last_cell_error
        return result

    def cancel(self):
        self.cancelled = True
        if self._cancel_event:
            self._cancel_event.set()


# ─── AI 摘要 Worker ──────────────────────────────────────────

class SummaryWorker(QThread):
    """后台提取 PDF 文本 → 调用 LLM 生成结构化摘要"""
    result = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path

    def run(self):
        try:
            doc = fitz.open(self.pdf_path)
            text = ""
            for i in range(min(8, len(doc))):
                text += doc[i].get_text()
            doc.close()
            text = text[:6000]  # 控制 token 用量

            from ui.ai_client import chat_completion
            system = (
                "你是学术论文摘要助手。请根据以下论文内容，用中文生成结构化摘要。\n"
                "严格按照以下格式输出（每个部分 2-3 句话）：\n\n"
                "📌 研究目标\n...\n\n"
                "🔬 研究方法\n...\n\n"
                "📊 核心结论\n...\n\n"
                "💡 主要贡献\n...\n\n"
                "如果论文不是中文的，请翻译为中文。"
            )
            result = chat_completion([
                {"role": "system", "content": system},
                {"role": "user", "content": f"论文内容：\n{text}"}
            ])
            self.result.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─── AI 问答 Worker ──────────────────────────────────────────

class QAWorker(QThread):
    """后台流式调用 LLM 问答"""
    chunk = pyqtSignal(str)     # 流式文本片段
    finished = pyqtSignal(str)  # 完整回答
    error = pyqtSignal(str)

    def __init__(self, messages: list, parent=None):
        super().__init__(parent)
        self.messages = messages

    def run(self):
        try:
            from ui.ai_client import chat_completion_stream
            full = ""
            for text in chat_completion_stream(self.messages):
                full += text
                self.chunk.emit(text)
            self.finished.emit(full)
        except Exception as e:
            self.error.emit(str(e))


# ─── 检查更新 Worker ──────────────────────────────────────────

class UpdateCheckWorker(QThread):
    """后台查询 GitHub 最新 Release, 只检测+返回信息, 不下载不替换任何文件"""
    found = pyqtSignal(str, str)  # 最新版本号(不带v前缀), release 页面 URL
    error = pyqtSignal(str)

    def run(self):
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/repos/AaronGIG/pdf2zh-desktop/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "pdf2zh-desktop"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            tag = (data.get("tag_name") or "").lstrip("vV").strip()
            url = data.get("html_url") or "https://github.com/AaronGIG/pdf2zh-desktop/releases/latest"
            if tag:
                self.found.emit(tag, url)
        except Exception as e:
            self.error.emit(str(e))
