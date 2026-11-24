from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path


def _asset_path() -> str:
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return str(root / "assets" / "index.html")


def main() -> None:
    multiprocessing.freeze_support()
    if "--self-test" in sys.argv:
        from app._launch_test import run
        run()
        return
    import webview

    from app.studio import Studio

    studio = Studio()
    window = webview.create_window(
        "Pdf2zh Studio", _asset_path(), js_api=studio,
        width=1360, height=880, min_size=(1040, 700), background_color="#f4f5f6",
        text_select=True, easy_drag=False,
    )
    studio._window = window
    webview.start(debug=False, gui="edgechromium", storage_path=str(studio._window_storage))


if __name__ == "__main__":
    main()
