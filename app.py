import os
import re

import requests
from flask import Flask, send_from_directory, request, jsonify

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

app = Flask(__name__, static_folder=".", static_url_path="")

@app.get("/")
def home():
    return send_from_directory(".", "index.html")

@app.get("/api/youtube")
def api_youtube():
    q = (request.args.get("q") or "electric unicycle review").strip()
    items = []

    try:
        url = "https://www.youtube.com/results?search_query=" + requests.utils.quote(q)
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()

        ids = re.findall(r'videoId":"([a-zA-Z0-9_-]{11})"', r.text)
        seen = set()
        for vid in ids:
            if vid in seen:
                continue
            seen.add(vid)
            items.append({"videoId": vid})
            if len(items) >= 20:
                break
    except Exception:
        items = []

    return jsonify({"query": q, "items": items})

@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)

if __name__ == "__main__":
    # DigitalOcean provides PORT
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
