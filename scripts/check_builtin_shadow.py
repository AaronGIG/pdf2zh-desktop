#!/usr/bin/env python3
"""检查 converter 里有没有内置函数被局部变量遮蔽（v2.3.30 事故的回归守卫）。

事故：core/site-packages/pdf2zh/converter.py 的 receive_layout 里原本就有
`for id, v in enumerate(var)`，v2.3.30 在同一函数上方加了 `id(child)`——Python 的
作用域按整个函数判定，`id` 就成了局部变量，那行一执行就 UnboundLocalError，
Windows 版 v2.3.30 一个字都翻不出来。py_compile 查不出这种错，只有运行到那行才炸。

这里用 symtable 做静态判定：找出每个目标函数里「既被当函数调用、又在本函数里被
赋值」的内置名字。发现即失败，打包前跑一下。

用法：python3 scripts/check_builtin_shadow.py
"""
from __future__ import annotations

import ast
import builtins
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (文件, 函数名)。Mac 那份镜像在 main_window.py 里叫 _new_receive_layout
TARGETS = [
    ("core/site-packages/pdf2zh/converter.py", "receive_layout"),
    ("mac/site-packages/pdf2zh/converter.py", "receive_layout"),   # 若将来纳入版本库
    ("ui/main_window.py", "_new_receive_layout"),
]

BUILTIN_NAMES = set(dir(builtins))


class _Scope(ast.NodeVisitor):
    """收集一个函数体内：被赋值的名字、被当作函数调用的名字。不进入嵌套函数。"""

    def __init__(self):
        self.assigned: set[str] = set()
        self.called: set[str] = set()

    def visit_FunctionDef(self, node):      # 嵌套函数是独立作用域，不看
        pass

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.assigned.add(node.id)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.called.add(node.func.id)
        self.generic_visit(node)

    # 推导式在 py3 里有自己的作用域，但 for 目标仍算在推导式内，不污染函数——跳过
    def visit_ListComp(self, node):
        for g in node.generators:
            self.visit(g.iter)
    visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp


def _find_func(tree: ast.AST, name: str):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def check(rel: str, func: str) -> list[str]:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return []
    tree = ast.parse(io.open(path, encoding="utf-8").read(), path)
    fn = _find_func(tree, func)
    if fn is None:
        return [f"{rel}: 找不到函数 {func}"]
    sc = _Scope()
    for stmt in fn.body:
        sc.visit(stmt)
    bad = sorted((sc.assigned & sc.called) & BUILTIN_NAMES)
    return [f"{rel}::{func}: 内置 `{n}` 既被赋值又被调用 → 运行到调用处会 UnboundLocalError"
            for n in bad]


def main() -> int:
    problems: list[str] = []
    for rel, func in TARGETS:
        problems += check(rel, func)
    if problems:
        print("❌ 内置函数遮蔽检查未通过：")
        for p in problems:
            print("   ", p)
        return 1
    print("✅ 内置函数遮蔽检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
