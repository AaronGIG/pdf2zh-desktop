"""Prompt 模板管理器 — 新增 / 保存 / 导入 / 导出"""

import json
from pathlib import Path


DEFAULT_TEMPLATES = {
    "默认（直译）": "",
    "学术论文": (
        "Translate as an academic paper. Keep technical terms in original "
        "language with {lang_out} explanation in parentheses. Use formal register. "
        "Preserve all mathematical notations {{v*}} unchanged."
    ),
    "口语化": (
        "Translate into conversational {lang_out}. Use simple words and short "
        "sentences. Make it easy to understand for non-experts."
    ),
    "引文保留": (
        "Translate the text to {lang_out}. Keep ALL citations, author names, "
        "years, journal names, and DOIs unchanged. Only translate descriptive text."
    ),
    "医学论文": (
        "Translate as a medical research paper. Keep drug names, gene names, "
        "protein names, and disease names in English with {lang_out} translation "
        "in parentheses on first occurrence."
    ),
    "法律文书": (
        "Translate as a legal document. Maintain precision and formal tone. "
        "Keep legal terms in original language with {lang_out} explanation. "
        "Preserve section numbering and references."
    ),
    "摘要精简": (
        "Translate to {lang_out}. Condense and simplify long sentences while "
        "preserving key information. Target 70% of original length."
    ),
}


class PromptTemplateManager:
    """管理用户自定义 Prompt 模板（存储在 ~/.config/pdf2zh/prompts.json）"""

    @staticmethod
    def path():
        from ui.config_manager import _config_dir
        return _config_dir() / "prompts.json"

    @classmethod
    def load_all(cls):
        """返回合并后的模板字典：默认 + 用户自定义"""
        templates = dict(DEFAULT_TEMPLATES)
        p = cls.path()
        if p.exists():
            try:
                user = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(user, dict):
                    templates.update(user)
            except Exception:
                pass
        return templates

    @classmethod
    def load_user(cls):
        """只返回用户自定义模板"""
        p = cls.path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @classmethod
    def save_template(cls, name: str, content: str):
        """保存/更新一个模板"""
        user = cls.load_user()
        user[name] = content
        cls.path().write_text(json.dumps(user, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def delete_template(cls, name: str):
        """删除用户自定义模板（不能删默认模板）"""
        if name in DEFAULT_TEMPLATES:
            return False
        user = cls.load_user()
        if name in user:
            del user[name]
            cls.path().write_text(json.dumps(user, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        return False

    @classmethod
    def import_from_file(cls, filepath: str):
        """从 JSON 文件导入模板"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            user = cls.load_user()
            user.update(data)
            cls.path().write_text(json.dumps(user, indent=2, ensure_ascii=False), encoding="utf-8")
            return len(data)
        return 0

    @classmethod
    def export_to_file(cls, filepath: str):
        """导出所有模板到 JSON 文件"""
        all_templates = cls.load_all()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(all_templates, f, indent=2, ensure_ascii=False)
        return len(all_templates)
