from app.studio import Studio
from pathlib import Path

def run():
    app = Studio()
    info = app.inspect_pdf(str(Path("test-sample.pdf").resolve()))
    assert info["pages"] == 1 and info["hasText"]
    assert info["preview"].startswith("data:image/jpeg")
    print("PACKAGED PDF IMPORT OK")
