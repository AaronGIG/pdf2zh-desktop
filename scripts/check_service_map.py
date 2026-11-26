#!/usr/bin/env python3
"""打包前检查：界面里每个翻译服务对应的内核名字，在内核里都真实存在。

v2.3.43 起加：Mac 版「OpenAI 兼容」「Ali Qwen」的服务名和内核对不上（openai-liked / qwen-mt），
选了就报 Unsupported translation service，从 v2.2.0 起一直坏着没人发现。
  Mac：ui/translate_worker.py 的 SERVICE_MAP 值 ↔ 系统 Python 里 pdf2zh 内核各翻译器的 name
  Win：gui_pyqt5.py 的 SERVICE_MAP 值（类名）↔ core/site-packages/pdf2zh/translator.py 里的类
不通过时退出码 1，sync_to_system_python.sh 会停下。
"""
import ast
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dict_literal(path, name):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f"{path} 里找不到 {name}")


def check_mac():
    import pdf2zh.translator as T
    conv = open(os.path.join(os.path.dirname(T.__file__), "converter.py"), encoding="utf-8").read()
    i = conv.index("for translator in [")
    classes = re.findall(r"(\w+Translator)", conv[i:conv.index("]:", i)])
    names = {getattr(T, c).name for c in classes if hasattr(T, c)}
    smap = _dict_literal(os.path.join(REPO, "ui", "translate_worker.py"), "SERVICE_MAP")
    return [f"Mac「{k}」→ {v}" for k, v in smap.items() if v not in names]


def check_win():
    src = open(os.path.join(REPO, "core", "site-packages", "pdf2zh", "translator.py"), encoding="utf-8").read()
    classes = set(re.findall(r"^class (\w+)\(", src, re.M))
    smap = _dict_literal(os.path.join(REPO, "core", "site-packages", "pdf2zh", "gui_pyqt5.py"), "SERVICE_MAP")
    return [f"Win「{k}」→ {v}" for k, v in smap.items() if v not in classes]


if __name__ == "__main__":
    bad = check_mac() + check_win()
    if bad:
        print("❌ 这些翻译服务在内核里找不到，选了会报 Unsupported translation service：")
        for b in bad:
            print("   ", b)
        sys.exit(1)
    print("✅ 翻译服务名检查通过（Mac 与 Windows）")
