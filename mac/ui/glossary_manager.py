"""术语库管理器 — 导入/导出/应用术语替换"""

import json
import csv
from pathlib import Path


DEFAULT_GLOSSARIES = {
    "学术通用": {
        "Abstract": "摘要", "Introduction": "引言", "Conclusion": "结论",
        "References": "参考文献", "Acknowledgments": "致谢", "Appendix": "附录",
        "Methodology": "研究方法", "Literature Review": "文献综述",
        "Discussion": "讨论", "Results": "结果", "Hypothesis": "假设",
        "Theorem": "定理", "Corollary": "推论", "Lemma": "引理", "Proof": "证明",
        "et al.": "等人", "i.e.": "即", "e.g.": "例如", "Fig.": "图", "Table": "表",
    },
    "计算机科学": {
        "machine learning": "机器学习", "deep learning": "深度学习",
        "neural network": "神经网络", "convolutional": "卷积",
        "transformer": "Transformer", "attention mechanism": "注意力机制",
        "gradient descent": "梯度下降", "backpropagation": "反向传播",
        "overfitting": "过拟合", "underfitting": "欠拟合",
        "reinforcement learning": "强化学习", "generative model": "生成模型",
    },
    "金融经济": {
        "shareholder": "股东", "activism": "积极主义", "hedge fund": "对冲基金",
        "portfolio": "投资组合", "derivative": "衍生品", "equity": "股权",
        "liquidity": "流动性", "volatility": "波动性", "arbitrage": "套利",
        "dividend": "股息", "leverage": "杠杆", "market capitalization": "市值",
    },
    "医学生物": {
        "clinical trial": "临床试验", "placebo": "安慰剂", "cohort": "队列",
        "prevalence": "患病率", "incidence": "发病率", "biomarker": "生物标志物",
        "pathogenesis": "发病机制", "prognosis": "预后", "etiology": "病因学",
        "in vivo": "体内", "in vitro": "体外", "efficacy": "疗效",
    },
    "不使用术语库": {},
}


class GlossaryManager:
    """
    术语库：存储为 JSON，格式 {"source_term": "target_term", ...}
    支持从 CSV/JSON 导入，翻译完成后自动替换。
    首次使用自动加载默认学术术语。
    存储路径: ~/.config/pdf2zh/glossary.json
    """

    @staticmethod
    def path():
        from ui.config_manager import _config_dir
        return _config_dir() / "glossary.json"

    @classmethod
    def load(cls):
        """加载当前激活的术语库"""
        p = cls.path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @classmethod
    def load_preset(cls, name):
        """加载预设术语库"""
        if name in DEFAULT_GLOSSARIES:
            cls.save(dict(DEFAULT_GLOSSARIES[name]))
            return DEFAULT_GLOSSARIES[name]
        return {}

    @classmethod
    def get_preset_names(cls):
        return list(DEFAULT_GLOSSARIES.keys())

    @classmethod
    def load_all_presets(cls):
        """加载所有预设 + 用户自定义"""
        all_g = dict(DEFAULT_GLOSSARIES)
        # 扫描用户自定义术语库文件
        from ui.config_manager import _config_dir
        user_dir = _config_dir() / "glossaries"
        if user_dir.exists():
            for f in user_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        all_g[f.stem] = data
                except Exception:
                    pass
        return all_g

    @classmethod
    def save(cls, glossary: dict):
        """保存术语库"""
        cls.path().write_text(
            json.dumps(glossary, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    @classmethod
    def add_term(cls, source: str, target: str):
        """添加一条术语"""
        g = cls.load()
        g[source] = target
        cls.save(g)

    @classmethod
    def remove_term(cls, source: str):
        """删除一条术语"""
        g = cls.load()
        if source in g:
            del g[source]
            cls.save(g)

    @classmethod
    def clear(cls):
        """清空术语库"""
        cls.save({})

    @classmethod
    def import_csv(cls, filepath: str):
        """
        从 CSV 导入术语。格式：
        source_term,target_term
        machine learning,机器学习
        """
        g = cls.load()
        count = 0
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[0].strip() and row[1].strip():
                    # 跳过标题行
                    if row[0].lower() in ('source', 'term', '原文', '术语'):
                        continue
                    g[row[0].strip()] = row[1].strip()
                    count += 1
        cls.save(g)
        return count

    @classmethod
    def import_json(cls, filepath: str):
        """从 JSON 导入术语"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            g = cls.load()
            g.update(data)
            cls.save(g)
            return len(data)
        return 0

    @classmethod
    def export_csv(cls, filepath: str):
        """导出术语库为 CSV"""
        g = cls.load()
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['source', 'target'])
            for src, tgt in g.items():
                writer.writerow([src, tgt])
        return len(g)

    @classmethod
    def export_json(cls, filepath: str):
        """导出术语库为 JSON"""
        g = cls.load()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(g, f, indent=2, ensure_ascii=False)
        return len(g)

    @classmethod
    def apply_glossary(cls, text: str):
        """对翻译结果应用术语替换"""
        g = cls.load()
        for source, target in g.items():
            text = text.replace(source, target)
        return text

    @classmethod
    def count(cls):
        return len(cls.load())
