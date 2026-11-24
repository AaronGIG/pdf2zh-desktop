from pathlib import Path

root = Path.cwd()
site = root / ".venv"

a = Analysis(
    ["app/main.py"], pathex=[str(root), str(root / "reference-core"), str(site)],
    binaries=[], datas=[
        ("app/assets", "assets"), ("resources", "resources"),
        (str(root / "resources/cuda-backend/vendor/cudart64_110.dll"), "resources/cuda-backend/bin"),
        (str(root / "resources/cuda-backend/vendor/cublas64_11.dll"), "resources/cuda-backend/bin"),
        (str(root / "resources/cuda-backend/vendor/cublasLt64_11.dll"), "resources/cuda-backend/bin"),
        (str(site / "llama_cpp/lib"), "llama_cpp/lib"),
        (str(site / "webview/js"), "webview/js"),
        (str(site / "webview/lib"), "webview/lib"),
        (str(site / "pythonnet"), "pythonnet"),
        (str(site / "rapidocr_onnxruntime"), "rapidocr_onnxruntime"),
    ],
    hiddenimports=[
        "webview.platforms.winforms", "llama_cpp", "pdf2zh.converter",
        "pdf2zh.high_level", "pdf2zh.translator", "babeldoc.assets.assets",
        "onnxruntime", "cv2", "fitz", "rapidocr_onnxruntime",
        "babeldoc.docvision.table_detection.rapidocr",
        "babeldoc._rust_il", "babeldoc.progress_monitor",
        "babeldoc.docvision.doclayout", "babeldoc.format.pdf.high_level",
        "babeldoc.format.pdf.parser_errors", "babeldoc.format.pdf.parser_resource",
        "babeldoc.format.pdf.result_merger", "babeldoc.format.pdf.split_manager",
        "babeldoc.format.pdf.translation_config",
        "babeldoc.format.pdf.document_il.il_version_1",
        "babeldoc.format.pdf.document_il.backend.pdf_creater",
        "babeldoc.rust_callback_bridge", "babeldoc.rust_layout_service",
        "babeldoc.rust_run_context", "babeldoc.rust_scan_service",
        "babeldoc.rust_translation_service", "babeldoc.rust_writer_service",
        "app.translator", "app.translation_worker", "app._launch_test", "clr_loader",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["pytest", "tkinter"],
    noarchive=False, optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Pdf2zhStudio",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, icon="resources/app.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Pdf2zhStudio")
