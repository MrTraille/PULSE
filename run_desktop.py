import threading
import webview
import atexit
import sys
from pathlib import Path
from label_ui import app, PROJECTS_DIR


# Chemin du fichier de log
ERROR_LOG = PROJECTS_DIR / "_pulse_error.log"

def clear_error_log():
    try:
        if ERROR_LOG.exists():
            ERROR_LOG.write_text("", encoding="utf-8")
    except Exception:
        pass

atexit.register(clear_error_log)

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent.resolve()

ICON_PATH = BASE_DIR / "icon.ico"


def start_flask():
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)

if __name__ == "__main__":
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    webview.create_window(
        "PULSE",
        "http://127.0.0.1:5000/",
        width=580,
        height=1080,
        min_size=(580, 875),
        x=50,
        y=0,
    )
    webview.start()
