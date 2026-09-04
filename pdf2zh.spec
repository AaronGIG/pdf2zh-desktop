# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for pdf2zh-desktop macOS"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
project_dir = os.path.dirname(os.path.abspath(SPEC))

# 完整收集 pdf2zh 及其关键依赖
pdf2zh_datas, pdf2zh_binaries, pdf2zh_hiddenimports = collect_all('pdf2zh')
onnx_datas, onnx_binaries, onnx_hiddenimports = collect_all('onnxruntime')
requests_datas, requests_binaries, requests_hiddenimports = collect_all('requests')
peewee_datas, peewee_binaries, peewee_hiddenimports = collect_all('peewee')
tenacity_datas, tenacity_binaries, tenacity_hiddenimports = collect_all('tenacity')

# requests 的核心依赖（collect_all('requests') 可能不会递归收集）
# v2.3.20: rapidocr_onnxruntime 之前只在 hiddenimports 里挂了个名字，但它只装在
# 仓库 core/site-packages 下、系统 python 没有，构建时 PyInstaller 解析不到就静默
# 跳过 → 打出来的 app 里 0 个 rapidocr 文件 → 勾了「OCR 识别」时 _ocr_preprocess
# 里 import rapidocr 直接 ImportError、走「OCR 模块未安装，跳过」→ 纯扫描件没加上
# 文字层就丢给翻译 → 什么都翻不出来（用户看到的「OCR 出结果但没翻译」）。
# 用 collect_all 连它自带的 3 个 .onnx 模型 + config.yaml 一起收进来；pyclipper、
# shapely 是 rapidocr 的 C 扩展依赖（检测框/多边形），也一并收。
_extra_collect = []
for pkg in ['urllib3', 'idna', 'certifi', 'charset_normalizer', 'tqdm',
            'pdfminer', 'openai', 'numpy',
            'rapidocr_onnxruntime', 'pyclipper', 'shapely']:
    try:
        d, b, h = collect_all(pkg)
        _extra_collect.append((d, b, h))
    except Exception:
        _extra_collect.append(([], [], []))
_extra_datas = sum([x[0] for x in _extra_collect], [])
_extra_binaries = sum([x[1] for x in _extra_collect], [])
_extra_hiddenimports = sum([x[2] for x in _extra_collect], [])

# babeldoc 可能未安装或非标准包，安全处理
try:
    babeldoc_datas, babeldoc_binaries, babeldoc_hiddenimports = collect_all('babeldoc')
except Exception:
    babeldoc_datas, babeldoc_binaries, babeldoc_hiddenimports = [], [], []

a = Analysis(
    [os.path.join(project_dir, 'ui', 'main_window.py')],
    pathex=[project_dir],
    binaries=pdf2zh_binaries + onnx_binaries + requests_binaries + peewee_binaries + tenacity_binaries + babeldoc_binaries + _extra_binaries,
    datas=[
        (os.path.join(project_dir, 'assets'), 'assets'),
        (os.path.join(project_dir, 'ui', 'quotes.py'), 'ui'),
    ] + pdf2zh_datas + onnx_datas + requests_datas + peewee_datas + tenacity_datas + babeldoc_datas + _extra_datas,
    hiddenimports=[
        # 本项目模块
        'ui', 'ui.main_window', 'ui.translate_worker',
        'ui.config_manager', 'ui.caring', 'ui.quotes',
        'ui.prompt_manager', 'ui.glossary_manager', 'ui.ai_client',
        # PyQt5
        'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui',
        'PyQt5.QtNetwork', 'PyQt5.sip',
        # pdf2zh 核心
        'pdf2zh', 'pdf2zh.translate', 'pdf2zh.doclayout',
        'pdf2zh.converter', 'pdf2zh.pdfinterp', 'pdf2zh.pdffont',
        # 翻译服务后端
        'requests', 'openai', 'deepl',
        'tencentcloud', 'tencentcloud.tmt',
        'azure.ai.translation.text',
        'ollama',
        # AI / ML
        'onnxruntime', 'onnx',
        'numpy',
        # PDF 处理
        'fitz', 'pymupdf',
        'pikepdf', 'pdfminer', 'pdfminer.six',
        'pdfminer.pdfparser', 'pdfminer.pdfdocument',
        'pdfminer.pdfpage', 'pdfminer.pdfinterp',
        'pdfminer.converter', 'pdfminer.layout',
        'lxml', 'lxml.etree',
        # babeldoc / 其他 pdf2zh 依赖
        'babeldoc',
        'rapidocr_onnxruntime',
        # 其他
        'json', 'csv', 'pathlib', 'subprocess',
        'PIL', 'PIL.Image',
        'huggingface_hub',
        'certifi', 'charset_normalizer', 'urllib3',
        'tqdm', 'regex', 'filelock',
    ] + pdf2zh_hiddenimports + onnx_hiddenimports + requests_hiddenimports + peewee_hiddenimports + tenacity_hiddenimports + babeldoc_hiddenimports + _extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大包
        'torch', 'torchvision', 'torchaudio',
        'spacy', 'stanza',
        'ctranslate2', 'argostranslate',
        'gradio', 'gradio_client',
        'matplotlib', 'scipy', 'pandas',
        'tkinter', '_tkinter',
        'IPython', 'jupyter',
        'pytest', 'setuptools', 'pip', 'wheel',
        # v2.3.15: 本机 site-packages 混进的开发环境残留（本地打包会被
        # PyInstaller 依赖扫描顺带打进去，把 app 从 282MB 撑到 791MB）。
        # 排除前逐个 grep 确认过引用情况——sklearn/h5py 全仓库零引用；
        # psycopg2 只在 peewee.py 里被 try/except ImportError 包着按需导入，
        # 排除后优雅降级。onnx 最初也在这个列表里，但 pdf2zh/doclayout.py 和
        # babeldoc/docvision/doclayout.py（版面检测，每次翻译都要走）里
        # `import onnx` 外层虽然也包了 try/except，却会重新 raise 而不是
        # 静默跳过——排掉 onnx 后这个 import 直接报错，把 TranslateWorker
        # 所在的 QThread 直接干死，PyQt5 默认不会把子线程里的未捕获异常
        # 冒泡到主线程，界面上完全看不出来，表现得跟卡死一模一样（构建
        # 后拿真实文档端到端测过才发现，没有报错、没有崩溃日志，翻译
        # 进度永远停在最开始）。onnx 是真实运行时依赖，不能排除。
        'sklearn', 'scikit-learn', 'h5py', 'psycopg2',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pdf2zh',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'assets', 'AppIcon.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='pdf2zh',
)

app = BUNDLE(
    coll,
    name='pdf2zh.app',
    icon=os.path.join(project_dir, 'assets', 'AppIcon.icns'),
    bundle_identifier='com.aarongig.pdf2zh',
    info_plist={
        'CFBundleName': 'pdf2zh',
        'CFBundleDisplayName': 'pdf2zh-desktop',
        'CFBundleVersion': '2.3.24',
        'CFBundleShortVersionString': '2.3.24',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
    },
)
