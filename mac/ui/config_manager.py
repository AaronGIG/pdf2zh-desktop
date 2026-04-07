"""配置与历史管理 — 持久化到 ~/.config/pdf2zh/ 目录"""

import json
import base64
import uuid
import hmac
import hashlib
import platform
import shutil
from pathlib import Path
from datetime import datetime


def _config_dir():
    """统一配置目录 ~/.config/pdf2zh/，首次使用自动创建 + 迁移旧文件"""
    d = Path.home() / ".config" / "pdf2zh"
    d.mkdir(parents=True, exist_ok=True)
    # 自动迁移旧版散落在 ~/ 下的配置文件
    _migrations = {
        "pdf2zh_gui_config.json": "config.json",
        "pdf2zh_history.json": "history.json",
        "pdf2zh_glossary.json": "glossary.json",
        "pdf2zh_prompts.json": "prompts.json",
    }
    for old_name, new_name in _migrations.items():
        old = Path.home() / old_name
        new = d / new_name
        if old.exists() and not new.exists():
            shutil.move(str(old), str(new))
    # 迁移术语库目录
    old_gdir = Path.home() / "pdf2zh_glossaries"
    new_gdir = d / "glossaries"
    if old_gdir.exists() and not new_gdir.exists():
        shutil.move(str(old_gdir), str(new_gdir))
    return d


class UserConfigManager:
    """用户偏好配置（翻译服务、语言、线程、分块等）"""

    @staticmethod
    def path():
        return _config_dir() / "config.json"

    @classmethod
    def load(cls):
        p = cls.path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @classmethod
    def save(cls, cfg: dict):
        p = cls.path()
        p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def encode_sensitive(v: str) -> str:
        return base64.b64encode(v.encode()).decode()

    @staticmethod
    def decode_sensitive(v: str) -> str:
        try:
            return base64.b64decode(v).decode()
        except Exception:
            return ""

    # ── 骰子防作弊 ──

    @staticmethod
    def _machine_id():
        """简易机器指纹（node MAC + platform）"""
        return f"{uuid.getnode()}-{platform.node()}"

    @classmethod
    def _dice_sign(cls, date_str: str, pages: int, used: bool) -> str:
        """HMAC-SHA256 签名骰子状态"""
        key = f"pdf2zh-dice-{cls._machine_id()}".encode()
        msg = f"{date_str}|{pages}|{int(used)}".encode()
        return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16]

    @classmethod
    def dice_save(cls, cfg: dict):
        """带签名地保存骰子状态"""
        d = cfg.get("dice_date", "")
        p = cfg.get("dice_today_pages", 0)
        u = cfg.get("dice_used", False)
        cfg["dice_sig"] = cls._dice_sign(d, p, u)
        cls.save(cfg)

    @classmethod
    def dice_verify(cls, cfg: dict) -> bool:
        """校验骰子状态签名，被篡改返回 False"""
        d = cfg.get("dice_date", "")
        p = cfg.get("dice_today_pages", 0)
        u = cfg.get("dice_used", False)
        expected = cls._dice_sign(d, p, u)
        return hmac.compare_digest(cfg.get("dice_sig", ""), expected)

    @classmethod
    def dice_win_code(cls, date_str: str) -> str:
        """生成中奖验证码（8 位），作者可用同一机器指纹离线验证"""
        key = f"pdf2zh-winner-{cls._machine_id()}".encode()
        msg = f"WIN|{date_str}".encode()
        return hmac.new(key, msg, hashlib.sha256).hexdigest()[:8].upper()


class HistoryManager:
    """翻译历史记录 — 支持分组和标签（v2 数据格式）"""

    _EMPTY = {"version": 2, "records": [], "groups": [], "tags": []}

    @staticmethod
    def path():
        return _config_dir() / "history.json"

    # ── 核心读写 ──

    @classmethod
    def load_all(cls) -> dict:
        """加载完整数据结构（含 records/groups/tags）"""
        p = cls.path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                # v1 迁移：旧格式是纯 list
                if isinstance(data, list):
                    data = {"version": 2, "records": data, "groups": [], "tags": []}
                    cls.save_all(data)
                return data
            except Exception:
                return dict(cls._EMPTY)
        return dict(cls._EMPTY)

    @classmethod
    def load(cls) -> list:
        """向后兼容：返回 records 列表"""
        return cls.load_all().get("records", [])

    @classmethod
    def save_all(cls, data: dict):
        p = cls.path()
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def save(cls, records: list):
        """向后兼容：只更新 records"""
        data = cls.load_all()
        data["records"] = records
        cls.save_all(data)

    # ── 记录操作 ──

    @classmethod
    def add_record(cls, record: dict):
        data = cls.load_all()
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("timestamp", datetime.now().isoformat())
        record.setdefault("group_id", None)
        record.setdefault("tags", [])
        data["records"].insert(0, record)
        if len(data["records"]) > 200:
            data["records"] = data["records"][:200]
        cls.save_all(data)
        return record

    @classmethod
    def delete_record(cls, record_id: str):
        data = cls.load_all()
        data["records"] = [r for r in data["records"] if r.get("id") != record_id]
        cls.save_all(data)

    @classmethod
    def clear(cls):
        data = cls.load_all()
        data["records"] = []
        cls.save_all(data)

    # ── 分组操作 ──

    @classmethod
    def add_group(cls, name: str, icon: str = "📁") -> dict:
        data = cls.load_all()
        g = {"id": str(uuid.uuid4()), "name": name, "icon": icon,
             "order": len(data.get("groups", []))}
        data.setdefault("groups", []).append(g)
        cls.save_all(data)
        return g

    @classmethod
    def rename_group(cls, group_id: str, new_name: str):
        data = cls.load_all()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                g["name"] = new_name
                break
        cls.save_all(data)

    @classmethod
    def delete_group(cls, group_id: str):
        data = cls.load_all()
        data["groups"] = [g for g in data.get("groups", []) if g["id"] != group_id]
        for r in data["records"]:
            if r.get("group_id") == group_id:
                r["group_id"] = None
        cls.save_all(data)

    @classmethod
    def move_to_group(cls, record_id: str, group_id):
        data = cls.load_all()
        for r in data["records"]:
            if r.get("id") == record_id:
                r["group_id"] = group_id
                break
        cls.save_all(data)

    @classmethod
    def reorder_groups(cls, ordered_ids: list):
        """按给定 ID 顺序重排分组"""
        data = cls.load_all()
        id_map = {g["id"]: g for g in data.get("groups", [])}
        data["groups"] = [id_map[gid] for gid in ordered_ids if gid in id_map]
        for i, g in enumerate(data["groups"]):
            g["order"] = i
        cls.save_all(data)

    @classmethod
    def update_group_icon(cls, group_id: str, icon: str):
        data = cls.load_all()
        for g in data.get("groups", []):
            if g["id"] == group_id:
                g["icon"] = icon
                break
        cls.save_all(data)

    # ── 标签操作 ──

    @classmethod
    def add_tag(cls, name: str, color: str = "#FF9F0A") -> dict:
        data = cls.load_all()
        t = {"id": str(uuid.uuid4()), "name": name, "color": color}
        data.setdefault("tags", []).append(t)
        cls.save_all(data)
        return t

    @classmethod
    def delete_tag(cls, tag_id: str):
        data = cls.load_all()
        data["tags"] = [t for t in data.get("tags", []) if t["id"] != tag_id]
        for r in data["records"]:
            if tag_id in r.get("tags", []):
                r["tags"].remove(tag_id)
        cls.save_all(data)

    @classmethod
    def toggle_record_tag(cls, record_id: str, tag_id: str):
        data = cls.load_all()
        for r in data["records"]:
            if r.get("id") == record_id:
                tags = r.setdefault("tags", [])
                if tag_id in tags:
                    tags.remove(tag_id)
                else:
                    tags.append(tag_id)
                break
        cls.save_all(data)
