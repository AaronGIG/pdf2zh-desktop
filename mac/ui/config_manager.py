"""配置与历史管理 — 持久化到 ~/pdf2zh_gui_config.json 和 ~/pdf2zh_history.json"""

import json
import base64
import uuid
import hmac
import hashlib
import platform
from pathlib import Path
from datetime import datetime


class UserConfigManager:
    """用户偏好配置（翻译服务、语言、线程、分块等）"""

    @staticmethod
    def path():
        return Path.home() / "pdf2zh_gui_config.json"

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
    """翻译历史记录（最多 100 条）"""

    @staticmethod
    def path():
        return Path.home() / "pdf2zh_history.json"

    @classmethod
    def load(cls):
        p = cls.path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    @classmethod
    def save(cls, records: list):
        p = cls.path()
        p.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def add_record(cls, record: dict):
        records = cls.load()
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("timestamp", datetime.now().isoformat())
        records.insert(0, record)
        if len(records) > 100:
            records = records[:100]
        cls.save(records)
        return record

    @classmethod
    def delete_record(cls, record_id: str):
        records = [r for r in cls.load() if r.get("id") != record_id]
        cls.save(records)

    @classmethod
    def clear(cls):
        cls.save([])
