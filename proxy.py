"""Reverse proxy: sert le build web Flutter ET relaye l'API backend.

Config via env : CAHIER_API_ORIGIN, CAHIER_AUTH_TOKEN, CAHIER_PROXY_PORT
"""
import mimetypes
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "web")
API_ORIGIN = os.getenv("CAHIER_API_ORIGIN", "http://127.0.0.1:8000")
AUTH_TOKEN = os.getenv("CAHIER_AUTH_TOKEN", "")
PROXY_PORT = int(os.getenv("CAHIER_PROXY_PORT", "8090"))
STATUS_PREFIXES = ("/status", "/status.html", "/changelog")
API_PREFIXES = ("/api/", "/docs", "/openapi.json", "/health", "/redoc")

_STATUS_HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Statut du projet Ecahier</title>
<style>
body{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:1rem}
h1{color:#1565c0}.card{background:#f5f5f5;border-radius:12px;padding:1.25rem;margin:1rem 0}
.status-ok{color:#2e7d32;font-weight:700}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:.4rem .2rem;border-bottom:1px solid #ddd}
.footer{color:#888;font-size:.8rem;margin-top:1rem}
</style></head><body>
<h1>Suivi du projet Ecahier</h1>
<div class="card"><h2>Etat du service</h2><p id="health">Verification...</p></div>
<div class="card"><h2>Dernieres modifications (git log)</h2>
<table id="commits"><tbody></tbody></table></div>
<p class="footer">Ecahier — <a href="/">Retour</a></p>
<script>
async function J(u){try{const r=await fetch(u,{cache:'no-store'});return r.ok?await r.json():null}catch(e){return null}}
(async()=>{const h=await J('/health');
document.getElementById('health').innerHTML=h?'<span class="status-ok">En ligne</span> — '+h.app+' v'+h.version+' (sync: '+h.sync_pending+')':'Hors ligne';
const c=await J('/status/commits');const t=document.querySelector('#commits tbody');
if(c){t.innerHTML=c.map(x=>'<tr><td style="font-family:monospace">'+x.hash.substring(0,8)+'</td><td>'+x.message+'</td><td style="color:#888">'+x.date+'</td></tr>').join('')}})();
</script></body></html>
"""



class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): pass
    def _is_api(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in API_PREFIXES)
    def _is_status(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in STATUS_PREFIXES)
    def _relay(self):
        body = None
        if "Content-Length" in self.headers:
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length)
        req = urllib.request.Request(API_ORIGIN + self.path, data=body, method=self.command)
        for h in ("Content-Type", "Authorization", "Accept"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        if AUTH_TOKEN and not req.has_header("Authorization"):
            req.add_header("Authorization", "Bearer " + AUTH_TOKEN)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = r.read()
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_error(502, "API injoignable")



class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): pass
    def _is_api(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in API_PREFIXES)
    def _is_status(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in STATUS_PREFIXES)
    def _relay(self):
        body = None
        if "Content-Length" in self.headers:
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length)
        req = urllib.request.Request(API_ORIGIN + self.path, data=body, method=self.command)
        for h in ("Content-Type", "Authorization", "Accept"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        if AUTH_TOKEN and not req.has_header("Authorization"):
            req.add_header("Authorization", "Bearer " + AUTH_TOKEN)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = r.read()
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_error(502, "API injoignable")

    def _status_page(self):
        p = self.path.split("?")[0]
        if p == "/status/commits":
            self._relay_commits()
            return
        data = _STATUS_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)
    def _relay_commits(self):
        try:
            req = urllib.request.Request(API_ORIGIN + "/status/commits", method="GET")
            if AUTH_TOKEN:
                req.add_header("Authorization", "Bearer " + AUTH_TOKEN)
            with urllib.request.urlopen(req, timeout=10) as r:
                payload = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except Exception:
            self.send_error(502, "API injoignable")



class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args): pass
    def _is_api(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in API_PREFIXES)
    def _is_status(self):
        p = self.path.split("?")[0]
        return any(p == x or p.startswith(x) for x in STATUS_PREFIXES)
    def _relay(self):
        body = None
        if "Content-Length" in self.headers:
            length = int(self.headers["Content-Length"])
            body = self.rfile.read(length)
        req = urllib.request.Request(API_ORIGIN + self.path, data=body, method=self.command)
        for h in ("Content-Type", "Authorization", "Accept"):
            if self.headers.get(h):
                req.add_header(h, self.headers[h])
        if AUTH_TOKEN and not req.has_header("Authorization"):
            req.add_header("Authorization", "Bearer " + AUTH_TOKEN)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = r.read()
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_error(502, "API injoignable")

    def _status_page(self):
        p = self.path.split("?")[0]
        if p == "/status/commits":
            self._relay_commits()
            return
        data = _STATUS_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)
    def _relay_commits(self):
        try:
            req = urllib.request.Request(API_ORIGIN + "/status/commits", method="GET")
            if AUTH_TOKEN:
                req.add_header("Authorization", "Bearer " + AUTH_TOKEN)
            with urllib.request.urlopen(req, timeout=10) as r:
                payload = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except Exception:
            self.send_error(502, "API injoignable")

    def _static(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"
        full = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if not full.startswith(WEB_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(full):
            full = os.path.join(WEB_DIR, "index.html")
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(500)
            return
        ctype, _ = mimetypes.guess_type(full)
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)
    def _handle(self):
        if self.command == "OPTIONS":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self._is_api():
            self._relay()
        elif self._is_status():
            self._status_page()
        elif self.command == "GET":
            self._static()
        else:
            self.send_error(405)
    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _handle

if __name__ == "__main__":
    print("Proxy demarre - web: " + WEB_DIR)
    print("API origin: " + API_ORIGIN + "  |  Port: " + str(PROXY_PORT))
    print("Auth token: " + ("active" if AUTH_TOKEN else "desactive (dev)"))
    print("URL: http://localhost:" + str(PROXY_PORT) + "  |  Statut: /status")
    ThreadingHTTPServer(("0.0.0.0", PROXY_PORT), Handler).serve_forever()
