#!/usr/bin/env python3
"""生成一键更新用的清单和增量包（v2.3.42 起每次发布都要跑，Mac / Win 各一次）。

用法：
  python3 scripts/make_update.py --platform win --version 2.3.43 \
      --new ~/pdf2zh_build/pkg/pdf2zh-desktop-win-v2.3.43.zip \
      --base 2.3.42=~/pdf2zh_build/pkg/pdf2zh-desktop-win-v2.3.42.zip \
      --notes-file 更新说明.txt --out ~/pdf2zh_build/pkg/

--base 填所有「已经带自动更新功能」的旧版本完整包（v2.3.42 及以后），能填多少填多少：
清单里没有的版本只能提示用户手动下载。输出：
  update-<平台>.json          清单（文件名固定，releases/latest/download/ 总能取到最新）
  update-<平台>-v<版本>.zip   增量包 = 各旧版本需要换的文件的合集（都取新版本的内容）
"""
import argparse
import hashlib
import json
import plistlib
import re
import stat
import sys
import zipfile
from pathlib import Path

RELEASE_BASE = "https://github.com/AaronGIG/pdf2zh-desktop/releases"
PREFIX = {"win": "pdf2zh-desktop-win/", "mac": "pdf2zh.app/"}
SKIP_DIRS = ("__MACOSX/", "_update/", "pdf2zh_files/")


def read_tree(zpath, plat):
    """{安装目录内相对路径: (sha256 或 'link:目标', ZipInfo)}"""
    pre = PREFIX[plat]
    out = {}
    with zipfile.ZipFile(zpath) as zf:
        for zi in zf.infolist():
            if zi.is_dir() or not zi.filename.startswith(pre):
                continue
            rel = zi.filename[len(pre):]
            if not rel or rel.startswith(SKIP_DIRS):
                continue
            data = zf.read(zi)
            mode = zi.external_attr >> 16
            key = ("link:" + data.decode("utf-8", "replace")) if stat.S_ISLNK(mode) else hashlib.sha256(data).hexdigest()
            out[rel] = (key, zi)
    return out


def version_in(zpath, plat):
    pre = PREFIX[plat]
    with zipfile.ZipFile(zpath) as zf:
        if plat == "mac":
            return plistlib.loads(zf.read(pre + "Contents/Info.plist"))["CFBundleShortVersionString"]
        src = zf.read(pre + "core/site-packages/pdf2zh/gui_pyqt5.py").decode("utf-8")
        return re.search(r'^APP_VERSION = "([\d.]+)"', src, re.M).group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=["win", "mac"])
    ap.add_argument("--version", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--base", action="append", default=[], help="旧版本号=完整包路径，可重复")
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mirror", action="append", default=[], help="额外的下载地址前缀（国内镜像），排在 GitHub 前面")
    a = ap.parse_args()
    plat, ver = a.platform, a.version
    notes = Path(a.notes_file).read_text(encoding="utf-8").strip() if a.notes_file else a.notes
    out = Path(a.out).expanduser(); out.mkdir(parents=True, exist_ok=True)

    real = version_in(a.new, plat)
    if real != ver:
        sys.exit(f"❌ 新包里的版本号是 {real}，不是 {ver}")
    new = read_tree(a.new, plat)
    print(f"新版本 v{ver}：{len(new)} 个文件")

    bases, union = {}, set()
    for spec in a.base:
        bver, bzip = spec.split("=", 1)
        bzip = str(Path(bzip).expanduser())
        bv_real = version_in(bzip, plat)
        if bv_real != bver:
            sys.exit(f"❌ {bzip} 里的版本号是 {bv_real}，不是 {bver}")
        old = read_tree(bzip, plat)
        changed = sorted(r for r, (k, _) in new.items() if old.get(r, (None,))[0] != k)
        deleted = sorted(r for r in old if r not in new)
        links = [r for r in changed if new[r][0].startswith("link:")]
        if links:
            print(f"  ⚠️ v{bver}：有符号链接变化 {links[:3]}，这个版本只能手动更新")
            continue
        bases[bver] = {"changed": changed, "deleted": deleted}
        union.update(changed)
        size = sum(new[r][1].file_size for r in changed)
        print(f"  v{bver} → v{ver}：换 {len(changed)} 个（{size / 1e6:.1f} MB）、删 {len(deleted)} 个")

    pname = f"update-{plat}-v{ver}.zip"
    ppath = out / pname
    if union:
        with zipfile.ZipFile(a.new) as src, zipfile.ZipFile(ppath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dst:
            for rel in sorted(union):
                zi = new[rel][1]
                nzi = zipfile.ZipInfo(rel, date_time=zi.date_time)
                nzi.external_attr = zi.external_attr
                nzi.compress_type = zipfile.ZIP_DEFLATED
                dst.writestr(nzi, src.read(zi))
        psize, psha = ppath.stat().st_size, hashlib.sha256(ppath.read_bytes()).hexdigest()
    else:   # 没有可自动升级的旧版本（例如第一个带自动更新的版本）：只发清单，不发增量包
        pname, psize, psha = "", 0, ""
    manifest = {
        "schema": 1, "platform": plat, "version": ver, "notes": notes,
        "release_url": f"{RELEASE_BASE}/tag/v{ver}",
        "mirrors": [m.rstrip("/") + "/" for m in a.mirror] + [f"{RELEASE_BASE}/download/v{ver}/"],
        "patch": {"name": pname, "size": psize, "sha256": psha,
                  "hashes": {r: new[r][0] for r in sorted(union)}},
        "bases": bases,
        "full": {"name": Path(a.new).name},
    }
    mpath = out / f"update-{plat}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {mpath.name}（支持 {len(bases)} 个旧版本自动更新）" + (f"+ {pname}（{psize / 1e6:.2f} MB）" if pname else "，不需要增量包"))


if __name__ == "__main__":
    main()
