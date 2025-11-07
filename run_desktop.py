import threading
import webview
from label_ui import app

def start_flask():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    webview.create_window(
        "PULSE",
        "http://127.0.0.1:5000/",
        width=580,
        height=875,
        min_size=(580, 875),
        x=50,
        y=50,
    )
    webview.start()
