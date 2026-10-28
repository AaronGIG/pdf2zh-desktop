#!/usr/bin/env python3
"""Windows 发布包重打：以上一版发布 zip 为基底，把包内所有「与仓库已跟踪文件内容不同」的条目
同步成仓库版本，其余条目逐字节原样拷贝。

为什么要这个脚本：本机没装 Git LFS，exe/dll/pyd/onnx 在工作树里只是指针存根，Windows 包只能在
上一版 zip 上替换文件重打。过去靠手工挑「这次改了哪几个 .py」，漏换的非 .py 文件会一直跟着发出去：
  - 7 个 .bat 一直是 LF 行尾，cmd 解析报错满屏（v2.3.34 才修）
  - 一键安装用的 assets/pdf2zh-connector.xpi 停在 1.0.19，Zotero 10 下被禁用（issue #34，v2.3.36 修）
  - supporters.txt 少了后来加的支持者
现在不再手工挑：凡是仓库跟踪、包里也有的文件，内容不一致就同步。

规则：
  * 文本文件（前 8KB 无 NUL）比较时统一行尾；写回时沿用包内原条目的行尾（原来是 CRLF 就转 CRLF）。
  * 二进制文件逐字节比较、逐字节替换。
  * Git LFS 指针存根跳过（工作树里没有真文件，无法同步，也就不会把存根写进包）。
  * 不删除条目；仓库里新增的运行时文件要手工确认后用 --add 加（脚本会列出疑似缺失）。

用法：
  python3 scripts/repack_win.py --base 上一版.zip --out 新版.zip [--add 仓库相对路径 ...]
  python3 scripts/repack_win.py --check 某版.zip        # 只检查，有过期文件就退出码 1
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFIX = "pdf2zh-desktop-win/"


def _is_text(b):
    return b"\0" not in b[:8192]


def _norm(b):
    return b.replace(b"\r\n", b"\n") if _is_text(b) else b


def _tracked():
    out = subprocess.check_output(["git", "-C", REPO, "ls-files", "-z"])
    return [f for f in out.decode("utf-8").split("\0") if f]


def stale_entries(zf):
    """返回 [(包内条目名, 仓库相对路径, 仓库字节)]：包里有、仓库跟踪、内容不同的文件。"""
    names = {n[len(PREFIX):]: n for n in zf.namelist() if n.startswith(PREFIX) and not n.endswith("/")}
    res = []
    for rel in _tracked():
        if rel not in names:
            continue
        path = os.path.join(REPO, rel)
        if not os.path.isfile(path):
            continue
        repo_b = open(path, "rb").read()
        if repo_b.startswith(b"version https://git-lfs"):
            continue
        if _norm(repo_b) != _norm(zf.read(names[rel])):
            res.append((names[rel], rel, repo_b))
    return res


def suspect_missing(zf):
    """仓库里有、包里没有的运行时文件（只看我们自己的代码、assets 和根目录启动文件）。"""
    names = {n[len(PREFIX):] for n in zf.namelist() if n.startswith(PREFIX)}
    out = []
    for rel in _tracked():
        if rel in names:
            continue
        if (rel.startswith("core/site-packages/pdf2zh/") and "__pycache__" not in rel) \
                or rel.startswith("assets/") \
                or ("/" not in rel and rel.endswith((".bat", ".vbs", ".py", ".txt", ".exe"))):
            out.append(rel)
    return out


def repack(base, out, add=()):
    zo = zipfile.ZipFile(base)
    stale = {name: (rel, b) for name, rel, b in stale_entries(zo)}
    now = time.localtime()[:6]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zn:
        for info in zo.infolist():
            if info.filename in stale:
                rel, repo_b = stale[info.filename]
                old_b = zo.read(info.filename)
                if _is_text(repo_b):
                    data = repo_b.replace(b"\r\n", b"\n")
                    if b"\r\n" in old_b:
                        data = data.replace(b"\n", b"\r\n")
                else:
                    data = repo_b
                ni = zipfile.ZipInfo(info.filename, date_time=now)
                ni.external_attr = info.external_attr
                ni.create_system = info.create_system
                ni.compress_type = zipfile.ZIP_DEFLATED
                zn.writestr(ni, data)
            else:
                zn.writestr(info, zo.read(info.filename), compress_type=info.compress_type)
        for rel in add:   # 手工确认要加的新文件（仓库原样字节）
            ni = zipfile.ZipInfo(PREFIX + rel, date_time=now)
            ni.external_attr = 0o644 << 16
            ni.compress_type = zipfile.ZIP_DEFLATED
            zn.writestr(ni, open(os.path.join(REPO, rel), "rb").read())
    return sorted(rel for rel, _ in stale.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--out")
    ap.add_argument("--check")
    ap.add_argument("--add", action="append", default=[], help="新增到包里的仓库文件（相对路径），可重复")
    a = ap.parse_args()

    if a.check:
        zf = zipfile.ZipFile(a.check)
        st = stale_entries(zf)
        miss = suspect_missing(zf)
        for _, rel, _ in st:
            print("  过期:", rel)
        for rel in miss:
            print("  疑似缺失:", rel)
        print(f"过期 {len(st)} 个，疑似缺失 {len(miss)} 个")
        sys.exit(1 if st else 0)

    if not (a.base and a.out):
        ap.error("需要 --base 和 --out，或者 --check")
    names0 = set(zipfile.ZipFile(a.base).namelist())
    for rel in a.add:
        if not os.path.isfile(os.path.join(REPO, rel)) or rel not in _tracked():
            ap.error(f"--add {rel}：不是仓库里已跟踪的文件")
        if PREFIX + rel in names0:
            ap.error(f"--add {rel}：包里已经有了")
    changed = repack(a.base, a.out, a.add)
    print(f"同步了 {len(changed)} 个文件:")
    for rel in changed:
        print("  *", rel)
    for rel in a.add:
        print("  + 新增", rel)

    # 自检：条目集合不变、zip 完整、再无过期文件
    zo, zn = zipfile.ZipFile(a.base), zipfile.ZipFile(a.out)
    assert zn.namelist() == zo.namelist() + [PREFIX + r for r in a.add], "条目列表变了"
    bad = zn.testzip()
    assert bad is None, f"zip 损坏: {bad}"
    left = stale_entries(zn)
    assert not left, f"重打后仍有过期文件: {[r for _, r, _ in left]}"
    miss = suspect_missing(zn)
    if miss:
        print("⚠️ 仓库里有、包里没有的运行时文件（需人工确认是否要加）:")
        for rel in miss:
            print("   ", rel)
    print(f"自检通过：条目 {len(zn.namelist())} 个（新增 {len(a.add)} 个），zip 完整，无过期文件。写出 {a.out}")


if __name__ == "__main__":
    main()
