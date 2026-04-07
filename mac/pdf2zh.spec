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
_extra_collect = []
for pkg in ['urllib3', 'idna', 'certifi', 'charset_normalizer', 'tqdm',
            'pdfminer', 'openai', 'numpy']:
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
        'ui.prompt_manager', 'ui.glossary_manager',
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
        'CFBundleVersion': '2.0.0',
        'CFBundleShortVersionString': '2.0.0',
        'LSMinimumSystemVersion': '13.0',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
    },
)
