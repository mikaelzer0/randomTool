#!/usr/bin/env python3
"""Mini-Access
    python Mini-Access.py                  avvia il programma (si apre nel browser)
    python Mini-Access.py --exe            crea dist/Mini-Access.exe (da Windows)
    python Mini-Access.py --exe --nome X   come sopra, con un altro nome

I dati si salvano in JSON nella cartella «dati» accanto al programma (o all'exe):
database.json, impostazioni.json, note.json. Se c'è un file Logo.png accanto,
diventa l'icona dell'exe. Per chiudere premi Ctrl+C (o chiudi la finestra).
"""
import argparse, json, shutil, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # True quando gira come .exe
BASE = Path(sys.executable if FROZEN else __file__).resolve().parent
DATI = BASE / "dati"
FILES = {"mdb": "database.json", "mui": "impostazioni.json", "mnote": "note.json"}
LOCK = threading.Lock()


def leggi(k):
    p = DATI / FILES[k]
    try:
        d = json.loads(p.read_text("utf-8"))
    except Exception:
        return None  # nessun file: l'app parte vuota
    return d.get("html") if k == "mnote" else json.dumps(d)


def scrivi(k, v):
    with LOCK:
        DATI.mkdir(exist_ok=True)
        d = {"html": v} if k == "mnote" else json.loads(v)
        p = DATI / FILES[k]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(p)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", tipo="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/load":
            self._send(200, json.dumps({k: leggi(k) for k in FILES}).encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGINA.encode(), "text/html")
        else:
            self._send(404)

    def do_POST(self):
        k = self.path.rsplit("/", 1)[-1]
        if not self.path.startswith("/api/save/") or k not in FILES:
            return self._send(404)
        try:
            scrivi(k, self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            self._send(204)
        except Exception:
            self._send(500)

    def log_message(self, *a):
        pass


# ---------- creazione dell'exe (ex crea_exe.py) ----------
def pip(*pacchetti):
    cmd = [sys.executable, "-m", "pip", "install", *pacchetti]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and "externally-managed-environment" in (r.stderr or ""):
        r = subprocess.run(cmd + ["--break-system-packages"], capture_output=True, text=True)
    if r.returncode != 0:
        print((r.stderr or r.stdout).strip()[-500:])
    return r.returncode == 0


def assicura(modulo, pacchetto):
    try:
        __import__(modulo)
    except ImportError:
        print(f"Installo {pacchetto}...")
        if not pip(pacchetto):
            sys.exit(f"Impossibile installare {pacchetto}.")


def crea_icona():
    logo = BASE / "Logo.png"
    if not logo.exists():
        print("[!] Logo.png non trovato: l'exe avrà l'icona di default.")
        return None
    assicura("PIL", "Pillow")
    from PIL import Image
    img = Image.open(logo).convert("RGBA")
    lato = max(img.size)  # quadrata, senza deformare
    quadro = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    quadro.paste(img, ((lato - img.width) // 2, (lato - img.height) // 2))
    ico = BASE / "_icona.ico"
    quadro.save(ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("Icona creata da Logo.png")
    return ico


def crea_exe(nome):
    assicura("PyInstaller", "pyinstaller")
    ico = crea_icona()
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
           "--name", nome, "--distpath", str(BASE / "dist"),
           "--workpath", str(BASE / "build"), "--specpath", str(BASE)]
    if ico:
        cmd += ["--icon", str(ico)]
    cmd.append(str(Path(__file__).resolve()))
    print("Creo l'exe (può richiedere qualche minuto)...")
    r = subprocess.run(cmd, cwd=BASE)
    exe = BASE / "dist" / (nome + (".exe" if sys.platform.startswith("win") else ""))
    for p in (BASE / "build", BASE / f"{nome}.spec", ico):
        if p and p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p and p.exists():
            p.unlink()
    if r.returncode or not exe.exists():
        print(f"\nCreazione exe FALLITA (codice {r.returncode}). Copia gli errori qui sopra per capire il motivo.")
        print(f"Python in uso: {sys.version.split()[0]} - PyInstaller funziona con versioni di Python recenti ma non ancora uscite.")
        input("Premi invio per chiudere...")
        sys.exit(1)
    print(f"\nFatto! Trovi l'exe qui: {exe}")
    input("Premi invio per chiudere...")


def main():
    if not FROZEN:
        ap = argparse.ArgumentParser(description="Mini-Access")
        ap.add_argument("--exe", action="store_true", help="crea l'eseguibile invece di avviare il programma")
        ap.add_argument("--nome", default="Mini-Access", help="nome dell'exe")
        a = ap.parse_args()
        scelta = ""
        if not a.exe and sys.stdin and sys.stdin.isatty():
            scelta = input("Mini-Access\n  Invio = avvia il programma\n  E     = crea l'exe\nScelta: ").strip().lower()
        if a.exe or scelta in ("e", "exe"):
            return crea_exe(a.nome)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    url = f"http://127.0.0.1:{srv.server_port}/"
    print(f"Mini-Access aperto su {url}\nI dati si salvano in: {DATI}\nPer chiudere premi Ctrl+C.", flush=True)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Chiuso.", flush=True)


PAGINA = r'''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Mini-Access</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&display=swap">
<script>
const DS=(()=>{let c={};try{const x=new XMLHttpRequest();x.open('GET','/api/load',false);x.send();c=JSON.parse(x.responseText)||{}}catch(e){}
let bad=0;return{getItem:k=>c[k]??null,setItem(k,v){c[k]=v;fetch('/api/save/'+k,{method:'POST',body:v,keepalive:true}).then(r=>{if(!r.ok)throw 0;bad=0}).catch(()=>{if(!bad++)alert('Salvataggio non riuscito: il programma Python è stato chiuso. Riaprilo per non perdere le modifiche.')})}}})();
</script>
<style>
:root{--bg:#e4e4e7;--tx:#101012;--mu:#66666e;--ac:#101012;--on:#fff;--ln:rgba(0,0,0,.09);--sf:rgba(255,255,255,.5);--ok:#1c7443;--er:#b3261e;--gw:255,255,255;--g1:rgba(var(--gw),calc(.72*var(--ga,1)));--g2:rgba(var(--gw),calc(.32*var(--ga,1)));--gb:rgba(255,255,255,.8);--sh:rgba(30,30,45,.12);--ink:0,0,0;color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#08080a;--tx:#f4f4f6;--mu:#9a9aa3;--ac:#f4f4f6;--on:#08080a;--ln:rgba(255,255,255,.1);--sf:rgba(255,255,255,.06);--ok:#7fd19b;--er:#ff8a80;--gw:255,255,255;--g1:rgba(var(--gw),calc(.13*var(--ga,1)));--g2:rgba(var(--gw),calc(.04*var(--ga,1)));--gb:rgba(255,255,255,.18);--sh:rgba(0,0,0,.55);--ink:255,255,255;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#08080a;--tx:#f4f4f6;--mu:#9a9aa3;--ac:#f4f4f6;--on:#08080a;--ln:rgba(255,255,255,.1);--sf:rgba(255,255,255,.06);--ok:#7fd19b;--er:#ff8a80;--gw:255,255,255;--g1:rgba(var(--gw),calc(.13*var(--ga,1)));--g2:rgba(var(--gw),calc(.04*var(--ga,1)));--gb:rgba(255,255,255,.18);--sh:rgba(0,0,0,.55);--ink:255,255,255;color-scheme:dark}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg,Canvas);color:var(--tx);font:var(--fs,14px)/1.45 var(--ff,"Instrument Sans","Helvetica Neue","Segoe UI",system-ui,sans-serif);-webkit-font-smoothing:antialiased}
#bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;overflow:hidden}
#bg svg{position:absolute;inset:0;width:100%;height:100%}
#bg .o{position:absolute;border-radius:50%;filter:blur(60px);background:radial-gradient(circle,rgba(var(--ink),.22),rgba(var(--ink),0) 68%)}
#bg .o:nth-child(1){width:46vmax;height:46vmax;left:-10vmax;top:-12vmax}
#bg .o:nth-child(2){width:38vmax;height:38vmax;right:-8vmax;bottom:-14vmax;animation-duration:42s;animation-direction:alternate-reverse}
#bg .o:nth-child(3){width:26vmax;height:26vmax;left:45%;top:30%;opacity:.55;animation-duration:50s}
@keyframes dr{to{transform:translate(9vmax,6vmax) scale(1.15)}}
.app{position:relative;z-index:1;display:grid;grid-template-columns:12.5rem minmax(0,1fr);gap:.8rem;padding:.8rem;min-height:100vh}
aside,.card,.sc{backdrop-filter:blur(var(--bl,14px));-webkit-backdrop-filter:blur(var(--bl,14px))}
aside,.card,.sc{background:linear-gradient(140deg,var(--g1),var(--g2));border:1px solid var(--gb);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),inset 0 -1px 0 rgba(var(--ink),.04),0 18px 50px -12px var(--sh)}
aside{position:sticky;top:.8rem;height:calc(100dvh - 1.6rem);border-radius:calc(var(--r,16px)*1.4);padding:.8rem .5rem;overflow-y:auto;display:flex;flex-direction:column;gap:.2rem}
aside h1{display:flex;align-items:center;gap:.65rem;font-size:1.15rem;font-weight:600;letter-spacing:-.02em;margin:.1rem .6rem .9rem}
aside h1::before{content:"";width:1.5rem;height:1.5rem;border-radius:50%;border:1.5px solid var(--tx);box-shadow:.45rem 0 0 -1px var(--bg,Canvas),.45rem 0 0 0 var(--tx);margin-right:.45rem;flex:none}
aside button{background:none;border:1px solid transparent;box-shadow:none;backdrop-filter:none;color:var(--mu);text-align:left;padding:.45rem .8rem;border-radius:calc(var(--r,16px)*.75);font:inherit;cursor:pointer;white-space:nowrap;transition:background .25s,color .25s,border-color .25s}
aside button:hover{background:rgba(var(--ink),.06);color:var(--tx);transform:none;box-shadow:none}
aside button.on{background:linear-gradient(140deg,var(--g1),var(--g2));border-color:var(--gb);color:var(--tx);font-weight:600;box-shadow:inset 0 1px 0 rgba(255,255,255,.4),0 6px 18px -8px var(--sh)}
#menu{display:flex;flex-direction:column;gap:.15rem}
main{padding:.3rem .4rem 2rem;min-width:0}
h2{margin:0 0 .8rem;font-size:1.6rem;font-weight:500;letter-spacing:-.03em;line-height:1.1}
h3{margin:1.1rem 0 .4rem;font-size:1rem;font-weight:600;letter-spacing:-.01em}
.mu{color:var(--mu)}
table{border-collapse:collapse;width:100%;background:none}
th,td{border:0;border-bottom:1px solid var(--ln);padding:var(--pd,.3rem) .6rem;text-align:left;white-space:nowrap}
tr:last-child td{border-bottom:0}
tr:hover td{background:rgba(var(--ink),.03)}
th{background:rgba(var(--ink),.05);font-weight:600}
th small{display:block;font-weight:400;color:var(--mu);font-size:.72rem}
td input:not([type=checkbox]),td select{border:0;background:transparent;box-shadow:none;backdrop-filter:none;width:100%;min-width:6rem;padding:.25rem .3rem;border-radius:8px}
td input:not([type=checkbox]):focus,td select:focus{background:rgba(var(--ink),.06)}
input,select,textarea{font:inherit;color:inherit;background:var(--sf);border:1px solid var(--gb);border-radius:calc(var(--r,16px)*.6);padding:.3rem .55rem;box-shadow:inset 0 1px 2px rgba(var(--ink),.05)}
input[type=checkbox]{accent-color:var(--ac);width:1rem;height:1rem;padding:0}
select option{color:#111;background:#fff}
button{font:inherit;border:1px solid var(--gb);background:linear-gradient(140deg,var(--g1),var(--g2));color:var(--tx);border-radius:var(--rb,999px);padding:.3rem .85rem;cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 4px 14px -6px var(--sh);transition:transform .2s,box-shadow .2s,background .2s}
button:hover{transform:translateY(-1px);box-shadow:inset 0 1px 0 rgba(255,255,255,.4),0 10px 22px -8px var(--sh)}
button:active{transform:translateY(0)}
button.pri,.chip.on{background:var(--ac);border-color:var(--ac);color:var(--on)}
button.x{color:var(--er)}
td button.x{padding:.2rem .6rem}
:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.row{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.5rem 0}
.sc{overflow-x:auto;border-radius:var(--r,16px)}
.card{border-radius:var(--r,16px);padding:.8rem 1rem;margin:.5rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:.5rem}
.grid label{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center}
.fl{display:grid;grid-template-columns:8rem 1fr;gap:.6rem;margin:.5rem 0;align-items:center}
.fl input:not([type=checkbox]),.fl select{width:100%}
.chip{margin:0 .3rem .5rem 0}
.chk{display:flex;flex-wrap:wrap;gap:.2rem .9rem;margin:.5rem 0}
textarea{width:100%;font-family:Consolas,"SF Mono",monospace;font-size:.85rem;border-radius:var(--r,16px);padding:.6rem .8rem}
.rl{list-style:none;padding:0}
.rl li{position:relative;background:linear-gradient(140deg,var(--g1),var(--g2));border:1px solid var(--gb);border-radius:var(--r,16px);padding:.45rem .8rem .45rem 1.3rem;margin:.35rem 0;display:flex;gap:.7rem;align-items:center}
.rl li::before{content:"";position:absolute;left:.6rem;top:50%;width:.4rem;height:.4rem;margin-top:-.2rem;border-radius:50%;border:1.5px solid var(--tx)}
.rl li .mu{margin-left:auto}
#m{position:fixed;z-index:5;top:calc(1rem + env(safe-area-inset-top,0px));right:1rem;max-width:min(26rem,calc(100vw - 2rem));padding:.65rem 1.1rem;border-radius:999px;font-weight:600;background:linear-gradient(140deg,var(--g1),var(--g2));border:1px solid var(--gb);backdrop-filter:blur(24px) saturate(170%);box-shadow:0 14px 40px -10px var(--sh)}
#m:empty{display:none}#m.ok{color:var(--ok)}#m.er{color:var(--er)}
ol{padding-left:1.3rem}
.paper{background:rgba(255,255,255,.93);color:#1a1a1a;border:1px solid #fff;padding:1.4rem;border-radius:16px;box-shadow:0 24px 60px -18px var(--sh)}
.paper h1{font-weight:500;letter-spacing:-.03em;margin-top:0}
.paper .sc{background:none;border:0;box-shadow:none;backdrop-filter:none;border-radius:0}
.paper table{background:#fff}.paper th{background:#f0f0f2;color:#1a1a1a}.paper td,.paper th{border:1px solid #dcdce0}.paper tr:hover td{background:none}
.tot{text-align:right;font-weight:600}.big{font-size:1.1rem;border-top:2px solid #1a1a1a;padding-top:.5rem}
@media(max-width:760px){.app{grid-template-columns:1fr;padding:.6rem;gap:.6rem}aside{position:static;height:auto;border-radius:22px;padding:.7rem}#menu{flex-direction:row;overflow-x:auto}aside h1{margin:0 .5rem .6rem}main{padding:.4rem .2rem 2rem}h2{font-size:1.4rem}.fl{grid-template-columns:1fr}}
@media print{#bg,aside,.ctl,#m{display:none!important}.app{display:block;padding:0}body{background:#fff}.paper{border:0;padding:0;box-shadow:none}}
.zb tr:nth-child(even) td{background:rgba(var(--ink),.045)}
#bg.no-o .o{display:none}
.sw{width:1.6rem;height:1.6rem;padding:0;border-radius:50%;border:2px solid var(--gb)}
.sw.on{outline:2px solid var(--tx);outline-offset:2px}
.fl input[type=range]{padding:0;accent-color:var(--ac)}
.fl input[type=color]{width:2.6rem;height:1.9rem;padding:0;border-radius:8px;cursor:pointer}
.fl b{min-width:2.4rem;text-align:right;font-weight:600}
.gh{margin:.9rem .8rem .25rem;font-size:.75rem;font-weight:600;color:var(--mu)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(10.5rem,1fr));gap:.7rem;margin-top:.6rem}
.tile{position:relative;min-height:7.5rem;border-radius:var(--r,16px);background:linear-gradient(140deg,var(--g1),var(--g2));border:1px solid var(--gb);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 12px 30px -14px var(--sh);backdrop-filter:blur(var(--bl,14px));transition:transform .2s}
.tile.w2{grid-column:span 2}.tile:hover{transform:translateY(-2px)}
.tile .tm{display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;gap:.6rem;width:100%;height:100%;min-height:inherit;padding:.9rem 1rem;background:none;border:0;box-shadow:none;border-radius:inherit;text-align:left;color:var(--tx);cursor:pointer;transform:none}
.tile .tm:hover{transform:none;box-shadow:none}
.ti{font-size:1.4rem;line-height:1;width:2.4rem;height:2.4rem;display:grid;place-items:center;border-radius:calc(var(--r,16px)*.7);background:rgba(var(--ink),.07);border:1px solid var(--ln)}
.tm b{font-size:1.02rem;font-weight:600;letter-spacing:-.01em}
.tm small{color:var(--mu)}.tm small.er{color:var(--er)}
.tile.em{outline:1.5px dashed var(--mu);outline-offset:2px;cursor:grab}
.tc{position:absolute;top:.4rem;right:.4rem;display:flex;gap:.2rem}
.tc button{padding:.05rem .45rem;font-size:.8rem}
.cb{width:min(36rem,100%);padding:.6rem 1.1rem;font-size:1rem;border-radius:var(--rb,999px)}
/* ===== Restyling: LED, leggibilità, spaziature, barra strumenti ===== */
@property --a{syntax:'<angle>';initial-value:0deg;inherits:false}
@keyframes sp{to{--a:360deg}}
:root{--l1:#00e5ff;--l2:#8b5cf6;--l3:#ff2d95;--l4:#ffb800}
button,.chip{display:inline-flex;align-items:center;justify-content:center;gap:.45em;line-height:1.25;min-height:2rem;font-variant-emoji:text;white-space:nowrap}
aside button{justify-content:flex-start;min-height:2.1rem}
.chk label{display:inline-flex;align-items:center;gap:.45rem}
td button.x,.tc button,.rl li button{min-width:2rem;padding-block:.15rem}
.ti{font-variant-emoji:text;font-family:"Segoe UI Symbol","Apple Symbols",system-ui,sans-serif}
.row{gap:.5rem}.fl span{font-weight:500}.fl b{font-variant-numeric:tabular-nums}
h2{font-weight:600}
main h2::after{content:"";display:block;width:2.8rem;height:3px;margin-top:.55rem;border-radius:3px;background:linear-gradient(90deg,var(--l1),var(--l2),var(--l3))}
h3{padding-bottom:.25rem;border-bottom:1px solid var(--ln)}
.card h3,.tile h3{border:0;padding:0}
table{border:1px solid rgba(var(--ink),.14)}
th{background:rgba(var(--ink),.09);font-size:.84rem;border-bottom:2px solid rgba(var(--ink),.2)}
td{border-bottom-color:rgba(var(--ink),.12)}
td+td,th+th{border-left:1px solid rgba(var(--ink),.07)}
input,select,textarea{border-color:rgba(var(--ink),.2)}
input:focus,select:focus,textarea:focus{outline:0;border-color:var(--l1);box-shadow:0 0 0 3px rgba(0,229,255,.22),0 0 14px rgba(139,92,246,.25)}
td input:not([type=checkbox]):focus,td select:focus{box-shadow:0 0 0 2px var(--l1)}
aside button.on{box-shadow:inset 3px 0 0 var(--l1),inset 0 1px 0 rgba(255,255,255,.4),0 6px 18px -8px var(--sh)}
.gh{display:flex;align-items:center;gap:.5rem;margin-top:1rem}.gh::after{content:"";flex:1;height:1px;background:var(--ln)}
aside h1::before{width:1.4rem;height:1.4rem;border:0;margin:0 .1rem 0 0;background:conic-gradient(from var(--a),var(--l1),var(--l2),var(--l3),var(--l4),var(--l1));box-shadow:0 0 12px rgba(0,229,255,.55);animation:sp 6s linear infinite}
/* contorni LED */
aside,.card,.tile,button.pri,.tbar{position:relative}aside{position:sticky}
aside::before,.card::before,.tile::before,button.pri::before,.tbar::before,aside::after,.card::after,.tile::after,button.pri::after,.tbar::after{content:"";position:absolute;inset:-1px;border-radius:inherit;padding:1.5px;pointer-events:none;background:conic-gradient(from var(--a),transparent 0 40%,var(--l1),var(--l2),var(--l3),var(--l4),transparent 92%);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:sp 7s linear infinite;opacity:var(--lo,1)}
aside::after,.card::after,.tile::after,button.pri::after,.tbar::after{inset:-3px;padding:4px;filter:blur(7px);opacity:calc(.45*var(--lo,1))}
.tile::before,.tile::after,.tile.em::before{animation-duration:9s}
html.noled :is(aside,.card,.tile,button.pri,.tbar)::before,html.noled :is(aside,.card,.tile,button.pri,.tbar)::after{display:none}
@media(prefers-reduced-motion:reduce){*,::before,::after{animation:none!important}}
/* barra strumenti */
.tbar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;padding:.45rem .6rem;margin-bottom:1rem;border-radius:calc(var(--r,16px)*1.2);background:linear-gradient(140deg,var(--g1),var(--g2));border:1px solid var(--gb);backdrop-filter:blur(var(--bl,14px));box-shadow:0 12px 30px -16px var(--sh)}
.tbar .sch{flex:1 1 11rem;min-width:9rem;text-align:center}
.seg{display:flex;gap:2px;padding:2px;border-radius:12px;background:rgba(var(--ink),.07)}
.ib{width:2.2rem;height:2.2rem;min-height:0;padding:0;border-radius:10px;border-color:transparent;background:none;box-shadow:none}
.ib:hover{background:rgba(var(--ink),.08);transform:none;box-shadow:none}.ib.on{background:rgba(var(--ink),.12)}
.ib svg{width:1.15rem;height:1.15rem;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.c1{color:#f08a24}.c2{color:#0a9be8}.c3{color:#e5333a}.c5{color:#1a8cff}
.fbar{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center;padding:.4rem .5rem;margin:.5rem 0;border-radius:12px;background:rgba(var(--ink),.05);border:1px solid var(--ln)}
.fbar select{padding:.2rem .4rem;font-size:.85rem;max-width:8.5rem}.fbar .ib{width:1.9rem;height:1.9rem}
.fbar .sp{width:1px;align-self:stretch;background:var(--ln);margin:0 .2rem}
.ed{min-height:50vh;outline:0;padding:1.6rem;font:15px/1.5 Palatino,"Palatino Linotype",Georgia,serif}
.ed:focus{box-shadow:0 0 0 3px rgba(0,229,255,.25),0 24px 60px -18px var(--sh)}
.ed blockquote{margin:.6rem 0;padding-left:1rem;border-left:3px solid var(--l2);color:#555}
.tsel{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.4rem 0 .8rem;padding:.4rem;border-radius:14px;background:rgba(var(--ink),.05);border:1px solid var(--ln)}
.tsel .chip{margin:0}.tsel .tf{width:10rem;border-radius:999px}
.bd{min-width:1.35rem;padding:0 .4rem;border-radius:999px;font-size:.72rem;font-weight:600;line-height:1.35rem;text-align:center;background:rgba(128,128,128,.28)}
.tbar .ts{max-width:10rem;font-weight:600;border-radius:999px}
/* ===== v3: tabelle, guida, barra semplificata ===== */
.hint{margin:.1rem 0 1rem;color:var(--mu);max-width:62ch}
.tbl td.n,.tbl th.n{width:2rem;text-align:right;color:var(--mu);font-variant-numeric:tabular-nums}
.tbl td.act{white-space:nowrap;text-align:right}.tbl td.act .ib{display:inline-flex;width:1.9rem;height:1.9rem}
.srt{cursor:pointer;user-select:none}.srt:hover{background:rgba(var(--ink),.15)}
.tt td{font-weight:600;background:rgba(var(--ink),.07)}
.rq input,.rq select{box-shadow:inset 0 0 0 1.5px var(--er)!important}
.sch2{flex:1 1 12rem;max-width:22rem}
details.card summary{cursor:pointer;font-weight:600}details.card[open] summary{margin-bottom:.6rem}
.more{position:relative}.more summary{cursor:pointer;list-style:none;padding:.3rem .9rem;border-radius:999px;border:1px solid var(--gb);background:rgba(var(--ink),.05);font-weight:500}
.more summary::-webkit-details-marker{display:none}
.mm{position:absolute;right:0;top:calc(100% + .4rem);z-index:6;min-width:14rem;padding:.4rem;display:flex;flex-direction:column;gap:.15rem;background:var(--bg,Canvas);border:1px solid var(--gb);border-radius:14px;box-shadow:0 18px 40px -12px var(--sh)}
.mm button{justify-content:flex-start;border-color:transparent;background:none;box-shadow:none;border-radius:10px;width:100%}.mm button:hover{background:rgba(var(--ink),.08);transform:none;box-shadow:none}
.mm label{display:flex;justify-content:space-between;align-items:center;gap:.6rem;padding:.3rem .8rem}
.steps{list-style:none;padding:0;margin:.6rem 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.6rem;counter-reset:s}
.steps li{counter-increment:s;display:flex;flex-direction:column;gap:.35rem;padding:.7rem;border-radius:14px;background:rgba(var(--ink),.05);border:1px solid var(--ln)}
.steps li::before{content:counter(s);width:1.6rem;height:1.6rem;display:grid;place-items:center;border-radius:50%;font-weight:600;font-size:.85rem;background:linear-gradient(135deg,var(--l1),var(--l2));color:#fff}
.steps li button{align-self:flex-start}
.gd{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:.6rem}
.gd dt{font-weight:600;margin-top:.5rem}.gd dd{margin:.1rem 0 0;color:var(--mu)}
kbd{font:inherit;font-size:.82rem;padding:.05rem .4rem;border-radius:6px;border:1px solid rgba(var(--ink),.25);background:rgba(var(--ink),.06)}
.gh{font-size:0;margin:.6rem .8rem}
.tsel{background:none;border:0;padding:0;margin:.2rem 0 .9rem;gap:.35rem}
.tg{display:inline-flex;gap:2px}.tg .chip{margin:0}.tdel{padding:.2rem .65rem;color:var(--er)}
.fd{margin-top:1rem}.fd summary{cursor:pointer;color:var(--mu)}.fd .row{margin:.4rem 0}
.tbl{max-height:68vh;overflow:auto}
.tbl th{position:sticky;top:0;z-index:2;background-color:var(--bg,Canvas);background-image:linear-gradient(rgba(var(--ink),.09),rgba(var(--ink),.09))}
.tbl tr:nth-child(even) td{background:rgba(var(--ink),.025)}.tbl tr:hover td{background:rgba(var(--ink),.06)}
.tbl tr.sl td{background:rgba(0,229,255,.13)}
.tbl td.n,.tbl th.n{width:2.2rem;text-align:center}
.tbl .adr td{text-align:center;cursor:pointer;color:var(--mu);border-top:1px dashed var(--ln);background:none}.tbl .adr:hover td{color:inherit}
.eur{text-align:right;font-variant-numeric:tabular-nums}.lk{display:flex;gap:.3rem;align-items:center}.lk a{text-decoration:none;color:var(--l2)}.opt{max-width:11rem}
.fd .ib:not(.on){opacity:.4}
.tm .mm{left:0;right:auto}
.tbl .fr th{position:static;background-image:none;font-weight:400;padding:.2rem .3rem}
.fr input{width:100%;min-width:4.5rem;padding:.15rem .4rem;font-size:.8rem;border-radius:8px}
.pg{display:flex;gap:.5rem;align-items:center;justify-content:center;margin:.7rem 0}.pg .ib{display:inline-flex;font-size:1.2rem}.pg .ib:disabled{opacity:.3}
.ro{background:rgba(var(--ink),.05);opacity:.85}
dialog{border:1px solid var(--gb,rgba(128,128,128,.4));border-radius:18px;background:var(--bg,Canvas);color:inherit;padding:.8rem 1.2rem 1.2rem;width:min(38rem,92vw)}
dialog::backdrop{background:rgba(0,0,0,.5);backdrop-filter:blur(3px)}
.dgh{text-align:right}dialog textarea{width:100%;min-height:12rem;font-family:ui-monospace,monospace;font-size:.85rem}dialog h3{margin-top:0}
</style>
</head>
<body>
<div id="bg" aria-hidden="true"><i class="o"></i><i class="o"></i><i class="o"></i><svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" fill="none"><defs>
<linearGradient id="g1" x1="0" x2="1"><stop offset="0" stop-color="rgb(var(--ink))" stop-opacity="0"/><stop offset=".3" stop-color="rgb(var(--ink))" stop-opacity=".85"/><stop offset=".65" stop-color="rgb(var(--ink))" stop-opacity=".12"/><stop offset="1" stop-color="rgb(var(--ink))" stop-opacity=".7"/></linearGradient>
<linearGradient id="g2" x1="1" x2="0"><stop offset="0" stop-color="rgb(var(--ink))" stop-opacity=".05"/><stop offset=".4" stop-color="rgb(var(--ink))" stop-opacity=".6"/><stop offset=".8" stop-color="rgb(var(--ink))" stop-opacity=".1"/><stop offset="1" stop-color="rgb(var(--ink))" stop-opacity="0"/></linearGradient></defs><path d="M0,211 C240,266 480,218 720,211 S1200,240 1440,280" stroke="url(#g1)" stroke-width="1.6" opacity=".5"><animate attributeName="d" dur="68s" repeatCount="indefinite" calcMode="spline" keySplines=".45 .05 .55 .95;.45 .05 .55 .95;.45 .05 .55 .95" keyTimes="0;.33;.66;1" values="M0,211 C240,266 480,218 720,211 S1200,240 1440,280;M0,77 C240,74 480,242 720,223 S1200,302 1440,294;M0,75 C240,28 480,208 720,135 S1200,52 1440,26;M0,211 C240,266 480,218 720,211 S1200,240 1440,280"/></path><path d="M0,375 C240,455 480,424 720,121 S1200,404 1440,302" stroke="url(#g2)" stroke-width="1.1" opacity=".4"><animate attributeName="d" dur="82s" repeatCount="indefinite" calcMode="spline" keySplines=".45 .05 .55 .95;.45 .05 .55 .95;.45 .05 .55 .95" keyTimes="0;.33;.66;1" values="M0,375 C240,455 480,424 720,121 S1200,404 1440,302;M0,331 C240,434 480,478 720,415 S1200,432 1440,180;M0,419 C240,107 480,370 720,132 S1200,130 1440,118;M0,375 C240,455 480,424 720,121 S1200,404 1440,302"/></path><path d="M0,337 C240,363 480,547 720,255 S1200,638 1440,477" stroke="url(#g1)" stroke-width="1.6" opacity=".5"><animate attributeName="d" dur="76s" repeatCount="indefinite" calcMode="spline" keySplines=".45 .05 .55 .95;.45 .05 .55 .95;.45 .05 .55 .95" keyTimes="0;.33;.66;1" values="M0,337 C240,363 480,547 720,255 S1200,638 1440,477;M0,407 C240,465 480,542 720,340 S1200,505 1440,359;M0,567 C240,390 480,495 720,242 S1200,579 1440,283;M0,337 C240,363 480,547 720,255 S1200,638 1440,477"/></path></svg></div>
<div class="app">
<aside><h1 id="appname">Mini-Access</h1><div id="menu"></div><button onclick="rst()" style="margin-top:auto;font-size:.8rem">Ripristina dati di esempio</button></aside>
<main><div id="m" role="status"></div><div id="v"></div></main>
</div>
<script>
const $=s=>document.querySelector(s);
const E=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const TY=['testo','numero','data','sì/no'];
const seed=()=>({tables:{},rel:[],macros:[],tiles:[]});
let db;try{db=JSON.parse(DS.getItem('mdb'))}catch{}db=db||seed();
if(db.tables.Clienti&&db.tables.Ordini&&db.tables.Clienti.r.length==3&&db.tables.Ordini.r.length==4&&db.macros.length==1&&db.macros[0].name=='Chiusura giornata')db=seed();
if(db.tiles&&db.tiles.length==8&&db.tiles[0].t=='Clienti'&&db.tiles[7].t=='Importa dati')db.tiles=[];
let HS=[],HL=JSON.stringify(db);const sv=()=>{typeof recalcAll=='function'&&recalcAll();const n=JSON.stringify(db);if(n!=HL){HS.push(HL);if(HS.length>40)HS.shift();HL=n}try{DS.setItem('mdb',n)}catch{}};
const T=(n=S.t)=>db.tables[n];
const fld=(tb,n)=>T(tb).f.find(f=>f.n==n);
const fk=(tb,n)=>{const r=db.rel.find(r=>r.a==tb+'.'+n);return r&&r.b.split('.')};
const nm=s=>s.trim().replace(/[^\wÀ-ÿ]+/g,'_');
const rpDef=t=>({t,g:'',s:''});
const qd=t=>({t,j:'',fs:null,ff:'',op:'=',fv:'',of:'',od:'crescente',ag:'',af:'',gb:''});
let S={tab:'tabelle',t:'Clienti',rec:0,macro:[],mn:'',io:''};
S.t=Object.keys(db.tables)[0];S.q=qd(S.t);S.rp={title:'Riepilogo',...(S.t?rpDef(S.t):{})};
const fmt=v=>v===true?'sì':v===false?'no':v??'';
const lab=(tb,row)=>{const f=T(tb).f.find(f=>f.t=='testo');return f?row[f.n]:row.id};
const disp=(tb,n,v)=>{const k=fk(tb,n);if(!k||v===''||v==null)return fmt(v);const row=T(k[0]).r.find(r=>r[k[1]]==v);return row?lab(k[0],row):'⚠ '+v};
const dq=(c,v)=>{const[tb,n]=c.split('.');return db.tables[tb]?disp(tb,n,v):fmt(v)};
function M(t,ok){const m=$('#m');m.textContent=t;m.className=ok?'ok':'er';clearTimeout(M.x);M.x=setTimeout(()=>m.textContent='',4500)}
function cast(f,v){if(f.t=='sì/no')return v===true||v=='true'||v=='sì';v=String(v).trim();if(v===''){if(f.q)throw `«${f.n}» è obbligatorio`;return ''}if(f.t=='numero'&&isNaN(v.replace(',','.')))throw `«${f.n}» deve essere un numero`;if(f.t=='data'&&!/^\d{4}-\d\d-\d\d$/.test(v))throw `«${f.n}» deve essere una data (AAAA-MM-GG)`;return f.t=='numero'?+v.replace(',','.'):v}
function used(tb,row){return db.rel.some(r=>{const[b1,b2]=r.b.split('.');if(b1!=tb||row[b2]==='')return false;const[a1,a2]=r.a.split('.');return T(a1).r.some(x=>x[a2]==row[b2])})}
const blank=tb=>{const t=T(tb),o={};t.f.forEach(f=>o[f.n]=f.t=='sì/no'?false:'');if(o.id!==undefined)o.id=Math.max(0,...t.r.map(r=>+r.id||0))+1;return o};
const cell=(tb,f,v,h)=>{const k=fk(tb,f.n),d=`data-f="${E(f.n)}"`;
if(k)return `<select ${d} onchange="${h}"><option value=""></option>${T(k[0]).r.map(r=>`<option value="${E(r[k[1]])}" ${r[k[1]]==v?'selected':''}>${E(lab(k[0],r))}</option>`).join('')}</select>`;
if(f.t=='calcolo')return `<input ${d} class="ro eur" readonly tabindex="-1" value="${v===''||v==null?'':Number(v).toLocaleString('it-IT',{maximumFractionDigits:2})}">`;
if(f.t=='scelta')return `<select ${d} class="pick" onchange="${h}"><option value=""></option>${v&&!(f.o||[]).includes(v)?`<option selected>${E(v)}</option>`:''}${(f.o||[]).map(o=>`<option ${o==v?'selected':''}>${E(o)}</option>`).join('')}</select>`;
if(f.cur)return `<input ${d} class="eur" inputmode="decimal" value="${v===''||v==null?'':Number(v).toFixed(2)}" onchange="${h}">`;
if(f.t=='link')return `<span class="lk"><input ${d} type="url" value="${E(v)}" onchange="${h}">${v?`<a href="${E(/^https?:/i.test(v)?v:'https://'+v)}" target="_blank" rel="noopener" title="Apri">↗</a>`:''}</span>`;
if(f.t=='sì/no')return `<input ${d} type="checkbox" ${v?'checked':''} onchange="${h}">`;
return `<input ${d} type="${f.t=='data'?'date':'text'}" value="${E(v)}" onchange="${h}">`};
const tbSel=(ed)=>`<div class="tsel">${Object.keys(db.tables).map(n=>`<span class="tg"><button class="chip ${n==S.t?'on':''}" onclick="S.t='${n}';S.rec=0;draw()">${E(n)}</button>${ed&&n==S.t?`<button class="chip tdel" title="Elimina tabella" aria-label="Elimina tabella" onclick="confirm('Eliminare «${n}» e tutti i suoi dati?')&&delT()">✕</button>`:''}</span>`).join('')}${ed?`<button class="chip" title="Nuova tabella" aria-label="Nuova tabella" onclick="newT()">+</button>`:''}</div>`;
const TABS=[['tabelle','Tabelle'],['relazioni','Relazioni'],['query','Query'],['maschere','Maschere'],['report','Report'],['macro','Macro'],['dati','Importa / Esporta']];
const GR={tabelle:'Dati',relazioni:'Dati',query:'Dati',maschere:'Dati',report:'Output',macro:'Output',dati:'Output',aspetto:'Impostazioni'};
function go(t){S.tab=t;draw()}
function draw(){if(!T())S.t=Object.keys(db.tables)[0];if(T()){if(!T(S.q.t))S.q=qd(S.t);if(S.q.j!==''&&!db.rel[S.q.j])S.q.j='';if(!T(S.rp.t))S.rp={title:S.rp.title,...rpDef(S.t)}}
$('#menu').innerHTML=(()=>{let p='';return TABS.map(([k,l])=>{const g=GR[k]||'',h=g!=p?`<div class="gh">${g}</div>`:'';p=g;return h+`<button class="${k==S.tab?'on':''}" onclick="go('${k}')">${l}</button>`}).join('')})();
$('#v').innerHTML=!Object.keys(db.tables).length&&['tabelle','query','maschere','report'].includes(S.tab)?V.vuoto():V[S.tab]()}
function rst(){if(!rst.c){rst.c=1;M('Premi di nuovo «Ripristina» per cancellare i tuoi dati');setTimeout(()=>rst.c=0,4000);return}rst.c=0;db=seed();S.t=undefined;S.rec=0;S.q=qd();S.rp={title:'Riepilogo'};S.macro=[];sv();draw()}

/* Tabelle */
function upd(i,n,el){const f=fld(S.t,n),t=T();try{const v=cast(f,el.type=='checkbox'?el.checked:el.value);if(n=='id'&&t.r.some((r,j)=>j!=i&&r.id==v))throw 'ID già esistente';t.r[i][n]=v;sv()}catch(e){M(e)}draw()}
function del(i){const row=T().r[i];if(used(S.t,row))return M('Impossibile eliminare: il record è collegato ad altre tabelle (integrità referenziale)');T().r.splice(i,1);sv();draw()}
function addRow(){T().r.push(blank(S.t));sv();draw()}
function addF(){const n=nm($('#nf').value);if(!n||fld(S.t,n))return M('Nome campo mancante o già usato');const f={n,t:$('#nt').value};if($('#nq').checked)f.q=1;T().f.push(f);T().r.forEach(r=>r[n]=f.t=='sì/no'?false:'');sv();draw()}
function addT(){const n=nm($('#nn').value);if(!n||db.tables[n])return M('Nome tabella mancante o già usato');db.tables[n]={f:[{n:'id',t:'numero',q:1},{n:'nome',t:'testo'}],r:[]};S.t=n;sv();draw()}
function delT(){const x=S.t;delete db.tables[x];db.rel=db.rel.filter(r=>!r.a.startsWith(x+'.')&&!r.b.startsWith(x+'.'));S.t=Object.keys(db.tables)[0];sv();draw()}
/* Relazioni */
function addR(){const a=$('#ra').value,b=$('#rb').value,[ta,fa]=a.split('.'),[tb,fb]=b.split('.');if(ta==tb)return M('Scegli campi di tabelle diverse');if(db.rel.some(r=>r.a==a&&r.b==b))return M('Relazione già presente');
if(T(ta).r.some(r=>r[fa]!==''&&!T(tb).r.some(y=>y[fb]==r[fa])))return M('Impossibile: ci sono valori in '+a+' senza corrispondenza in '+b);db.rel.push({a,b});sv();draw()}
/* Query */
function base(q){const t=T(q.t);let cols=t.f.map(f=>q.t+'.'+f.n),rows=t.r.map((r,i)=>{const o={_i:i};t.f.forEach(f=>o[q.t+'.'+f.n]=r[f.n]);return o});
if(q.j!==''){const r=db.rel[q.j],[ta,fa]=r.a.split('.'),[tb,fb]=r.b.split('.'),ot=q.t==ta?tb:ta,o=T(ot);cols=cols.concat(o.f.map(f=>ot+'.'+f.n));
rows=rows.flatMap(x=>o.r.filter(y=>q.t==ta?y[fb]==x[ta+'.'+fa]:y[fa]==x[tb+'.'+fb]).map(y=>{const z={...x};o.f.forEach(f=>z[ot+'.'+f.n]=y[f.n]);return z}))}
return{cols,rows}}
const test=(a,op,b)=>{if(b==='')return true;const n=a!==''&&a!=null&&!isNaN(a)&&!isNaN(b),x=n?+a:String(fmt(a)).toLowerCase(),y=n?+b:String(b).toLowerCase();return op=='='?x==y:op=='≠'?x!=y:op=='>'?x>y:op=='<'?x<y:String(x).includes(String(y))};
function run(){const q=S.q;let{cols,rows}=base(q);if(q.ff)rows=rows.filter(r=>test(r[q.ff],q.op,q.fv));
if(q.of)rows=[...rows].sort((a,b)=>(a[q.of]>b[q.of]?1:a[q.of]<b[q.of]?-1:0)*(q.od=='decrescente'?-1:1));
if(q.ag&&q.gb){const g={};rows.forEach(r=>(g[r[q.gb]]??=[]).push(r));const n=q.ag+(q.af?'('+q.af+')':'');cols=[q.gb,n];
rows=Object.entries(g).map(([k,a])=>{const s=a.reduce((s,r)=>s+(+r[q.af]||0),0),v=q.ag=='conteggio'?a.length:q.ag=='somma'?s:s/a.length;return{[q.gb]:k,[n]:Math.round(v*100)/100}})}
else if(q.fs)cols=cols.filter(c=>q.fs.includes(c));
return{cols,rows}}
function Q(k,v){const q=S.q;if(k=='t')S.q=qd(v);else{q[k]=v;if(k=='j'){q.fs=null;q.ff=q.of=q.gb=q.af=''}}draw()}
function tg(c){const q=S.q;q.fs=q.fs||base(q).cols;q.fs=q.fs.includes(c)?q.fs.filter(x=>x!=c):[...q.fs,c];draw()}
function expQ(){const{cols,rows}=run();S.io=toCSV([cols,...rows.map(r=>cols.map(c=>r[c]))]);S.tab='dati';draw()}
function bulk(d){const q=S.q,{rows}=run(),t=T(q.t),ix=new Set(rows.map(r=>r._i));
if(d){if(!q.ff)return M('Imposta un filtro prima di eliminare');let n=0;t.r=t.r.filter((r,i)=>{if(ix.has(i)&&!used(q.t,r)){n++;return false}return true});M(n+' record eliminati',1)}
else{const f=fld(q.t,$('#bf').value);try{const v=cast(f,$('#bv').value);ix.forEach(i=>t.r[i][f.n]=v);M(ix.size+' record aggiornati',1)}catch(e){return M(e)}}
sv();draw()}
/* Maschere */
function mv(d){S.rec=Math.max(0,Math.min(T().r.length-1,S.rec+d));draw()}
function newRec(){T().r.push(blank(S.t));S.rec=T().r.length-1;sv();draw()}
function saveRec(){const t=T(),o={};try{document.querySelectorAll('#frm [data-f]').forEach(el=>{const f=fld(S.t,el.dataset.f);o[f.n]=cast(f,el.type=='checkbox'?el.checked:el.value)});
if(o.id!==undefined&&t.r.some((r,j)=>j!=S.rec&&r.id==o.id))throw 'ID già esistente';
for(const f of t.f){const k=fk(S.t,f.n);if(k&&o[f.n]!==''&&!T(k[0]).r.some(r=>r[k[1]]==o[f.n]))throw `«${f.n}»: valore non presente in ${k[0]}`}
Object.assign(t.r[S.rec],o);sv();M('Record salvato',1);draw()}catch(e){M(e)}}
const sub=r=>db.rel.filter(x=>x.b.startsWith(S.t+'.')).map(x=>{const[a1,a2]=x.a.split('.'),k=x.b.split('.')[1],c=T(a1),rs=c.r.filter(y=>y[a2]==r[k]&&r[k]!=='');
return `<h3>Sottomaschera: ${E(a1)}</h3><div class="sc"><table><tr>${c.f.map(f=>`<th>${E(f.n)}</th>`).join('')}</tr>${rs.map(y=>`<tr>${c.f.map(f=>`<td>${E(disp(a1,f.n,y[f.n]))}</td>`).join('')}</tr>`).join('')||'<tr><td class="mu">Nessun record collegato</td></tr>'}</table></div>`}).join('');
/* Report e macro */
function R(k,v){if(k=='t')S.rp={...S.rp,...rpDef(v)};else S.rp[k]=v;draw()}
function addStep(){const a=$('#ma').value;S.macro.push({a,t:a=='msg'?$('#mx').value:$('#mt').value});draw()}
function saveM(){if(!S.mn.trim()||!S.macro.length)return M('Dai un nome e aggiungi almeno un passo');db.macros.push({name:S.mn.trim(),steps:S.macro});S.macro=[];S.mn='';sv();draw()}
function runM(i){let to=null;for(const s of db.macros[i].steps){if(s.a=='msg')M(s.t,1);else if(!T(s.t))return M('Tabella mancante: '+s.t);else if(s.a=='csv'){S.io=csv(s.t);to='dati'}else{S.t=s.t;S.rec=0;if(s.a=='report')S.rp={...S.rp,...rpDef(s.t)};to={tab:'tabelle',maschera:'maschere',report:'report'}[s.a]}}if(to)S.tab=to;draw()}
/* Import / Esporta */
const qt=v=>{v=v===true?'true':v===false?'false':String(v??'');return /[",;\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
const toCSV=m=>m.map(r=>r.map(qt).join(',')).join('\n');
const csv=tb=>{const t=T(tb);if(!t)return'';return toCSV([t.f.map(f=>f.n),...t.r.map(r=>t.f.map(f=>r[f.n]))])};
function parseCSV(s){const rows=[];let r=[],c='',q=false;for(let i=0;i<s.length;i++){const h=s[i];if(q){if(h=='"'){if(s[i+1]=='"'){c+='"';i++}else q=false}else c+=h}else if(h=='"')q=true;else if(h==','||h==';'){r.push(c);c=''}else if(h=='\n'){r.push(c);rows.push(r);r=[];c=''}else if(h!='\r')c+=h}if(c||r.length){r.push(c);rows.push(r)}return rows}
function impCSV(){const n=nm($('#ni').value);if(!n||db.tables[n])return M('Scegli un nome nuovo per la tabella');const m=parseCSV(S.io.trim()).filter(r=>r.some(c=>c!==''));if(m.length<2)return M('CSV non valido: servono intestazioni e almeno una riga');
const h=m[0].map(nm),b=m.slice(1);
const f=h.map((x,i)=>{const c=b.map(r=>(r[i]??'').trim()).filter(v=>v!=='');const t=c.length&&c.every(v=>!isNaN(v.replace(',','.')))?'numero':c.length&&c.every(v=>/^\d{4}-\d\d-\d\d$/.test(v))?'data':c.length&&c.every(v=>/^(true|false|sì|no)$/i.test(v))?'sì/no':'testo';return{n:x||'campo'+(i+1),t}});
db.tables[n]={f,r:b.map(r=>{const o={};f.forEach((g,i)=>{const v=(r[i]??'').trim();o[g.n]=g.t=='numero'?(v===''?'':+v.replace(',','.')):g.t=='sì/no'?/^(true|sì)$/i.test(v):v});return o})};
S.t=n;S.tab='tabelle';sv();M('Importate '+b.length+' righe',1);draw()}
function impJ(){try{const o=JSON.parse(S.io);if(!o.tables||!o.rel)throw 0;db=o;S.t=Object.keys(db.tables)[0];S.q=qd(S.t);S.rp={title:'Riepilogo',...(S.t?rpDef(S.t):{})};sv();M('Database ripristinato',1);draw()}catch{M('JSON non valido')}}
function rd(el){const f=el.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{S.io=r.result;draw()};r.readAsText(f)}

const V={
vuoto(){return `<h2>Nessuna tabella</h2><p class="mu">L'app è vuota. Crea la tua prima tabella per cominciare.</p><div class="row"><input id="nn" placeholder="nome della tabella" onkeydown="if(event.key=='Enter')addT()"><button class="pri" onclick="addT()">Crea tabella</button></div>`},
tabelle(){const t=T();return `<h2>Tabelle</h2>${tbSel()}<div class="sc"><table><tr>${t.f.map(f=>`<th>${E(f.n)}<small>${f.t}${f.q?' *':''}</small></th>`).join('')}<th></th></tr>
${t.r.map((r,i)=>`<tr>${t.f.map(f=>`<td>${cell(S.t,f,r[f.n],`upd(${i},'${f.n}',this)`)}</td>`).join('')}<td><button class="x" onclick="del(${i})" aria-label="Elimina riga">✕</button></td></tr>`).join('')}</table></div>
<div class="row"><button onclick="addRow()">+ Nuova riga</button><span class="mu">* campo obbligatorio</span></div>
<h3>Struttura della tabella</h3><div class="row"><input id="nf" placeholder="nome campo"><select id="nt">${TY.map(x=>`<option>${x}</option>`).join('')}</select><label><input type="checkbox" id="nq"> obbligatorio</label><button onclick="addF()">Aggiungi campo</button></div>
<div class="row"><input id="nn" placeholder="nuova tabella"><button onclick="addT()">Crea tabella</button><button class="x" onclick="delT()">Elimina «${E(S.t)}»</button></div>`},
relazioni(){const o=Object.keys(db.tables).flatMap(t=>T(t).f.map(f=>`<option>${E(t+'.'+f.n)}</option>`)).join('');
return `<h2>Relazioni</h2>
<ul class="rl">${db.rel.map((r,i)=>`<li><b>${E(r.a)}</b> → <b>${E(r.b)}</b><span class="mu">uno-a-molti</span><button class="x" onclick="db.rel.splice(${i},1);sv();draw()">✕</button></li>`).join('')||'<li class="mu">Nessuna relazione</li>'}</ul>
<div class="row"><select id="ra">${o}</select><span>→</span><select id="rb">${o}</select><button class="pri" onclick="addR()">Crea relazione</button></div>`},
query(){const q=S.q,{cols:all}=base(q),r=run(),sel=(k,a,b)=>`<select onchange="Q('${k}',this.value)">${b?'<option value=""></option>':''}${a.map(x=>`<option ${x==q[k]?'selected':''}>${E(x)}</option>`).join('')}</select>`;
const rl=db.rel.map((x,i)=>[x,i]).filter(([x])=>x.a.startsWith(q.t+'.')||x.b.startsWith(q.t+'.'));
return `<h2>Query</h2><div class="card grid">
<label>Tabella ${sel('t',Object.keys(db.tables))}</label>
<label>Unisci con <select onchange="Q('j',this.value)"><option value="">nessuna</option>${rl.map(([x,i])=>`<option value="${i}" ${String(i)==q.j?'selected':''}>${E(x.a)} = ${E(x.b)}</option>`).join('')}</select></label>
<label>Filtra ${sel('ff',all,1)} ${sel('op',['=','≠','>','<','contiene'])} <input value="${E(q.fv)}" onchange="Q('fv',this.value)" placeholder="valore"></label>
<label>Ordina ${sel('of',all,1)} ${sel('od',['crescente','decrescente'])}</label>
<label>Raggruppa per ${sel('gb',all,1)} calcola ${sel('ag',['conteggio','somma','media'],1)} di ${sel('af',all,1)}</label></div>
<div class="chk">${all.map(c=>`<label><input type="checkbox" ${(q.fs||all).includes(c)?'checked':''} onchange="tg('${c}')">${E(c)}</label>`).join('')}</div>
<div class="sc"><table><tr>${r.cols.map(c=>`<th>${E(c)}</th>`).join('')}</tr>${r.rows.map(x=>`<tr>${r.cols.map(c=>`<td>${E(dq(c,x[c]))}</td>`).join('')}</tr>`).join('')}</table></div>
<div class="row"><span class="mu">${r.rows.length} risultati</span><button onclick="expQ()">Esporta in CSV</button></div>
${!q.j&&!q.ag?`<div class="card"><b>Modifica in blocco</b> sui risultati<div class="row"><select id="bf">${T(q.t).f.map(f=>`<option>${E(f.n)}</option>`).join('')}</select><span>=</span><input id="bv" placeholder="nuovo valore"><button onclick="bulk(0)">Aggiorna</button><button class="x" onclick="bulk(1)">Elimina risultati</button></div></div>`:''}`},
maschere(){const t=T(),n=t.r.length;if(S.rec>=n)S.rec=Math.max(0,n-1);const r=t.r[S.rec];
return `<h2>Maschere</h2>${tbSel()}${r?`<div class="card" id="frm">${t.f.map(f=>`<label class="fl"><span>${E(f.n)}${f.q?' *':''}</span>${cell(S.t,f,r[f.n],'')}</label>`).join('')}</div>
<div class="row"><button onclick="mv(-1)" aria-label="Precedente">◀</button><span>Record ${S.rec+1} di ${n}</span><button onclick="mv(1)" aria-label="Successivo">▶</button><button onclick="newRec()">+ Nuovo</button><button class="pri" onclick="saveRec()">Salva</button><button class="x" onclick="del(${S.rec})">Elimina</button></div>${sub(r)}`:'<p>Nessun record. <button onclick="newRec()">+ Nuovo</button></p>'}`},
report(){const p=S.rp,t=T(p.t),g=p.g,s=p.s,fs=t.f.map(f=>f.n),ns=t.f.filter(f=>f.t=='numero').map(f=>f.n);
const nf=n=>n.toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2}),o=(a,v,b)=>(b?'<option value=""></option>':'')+a.map(x=>`<option ${x==v?'selected':''}>${E(x)}</option>`).join('');
const grp={};t.r.forEach(r=>(grp[g?String(disp(p.t,g,r[g])):'Tutti i record']??=[]).push(r));const sum=a=>a.reduce((x,r)=>x+(+r[s]||0),0);
return `<h2>Report</h2><div class="card grid ctl"><label>Tabella <select onchange="R('t',this.value)">${o(Object.keys(db.tables),p.t)}</select></label><label>Raggruppa per <select onchange="R('g',this.value)">${o(fs,g,1)}</select></label><label>Somma <select onchange="R('s',this.value)">${o(ns,s,1)}</select></label><label>Titolo <input value="${E(p.title)}" onchange="R('title',this.value)"></label><button class="pri" onclick="window.print()">Stampa / salva PDF</button></div>
<div class="paper"><h1>${E(p.title)}</h1><p>${new Date().toLocaleDateString('it-IT')}</p>
${Object.keys(grp).sort().map(k=>{const a=grp[k];return `<h3>${E(k)}</h3><div class="sc"><table><tr>${fs.map(f=>`<th>${E(f)}</th>`).join('')}</tr>${a.map(r=>`<tr>${fs.map(f=>`<td>${E(disp(p.t,f,r[f]))}</td>`).join('')}</tr>`).join('')}</table></div><p class="tot">${a.length} record${s?', totale '+E(s)+': '+nf(sum(a)):''}</p>`}).join('')}
<p class="tot big">Totale generale: ${t.r.length} record${s?', '+nf(sum(t.r)):''}</p></div>`},
macro(){const A={tab:'Apri tabella',maschera:'Apri maschera',report:'Apri report',csv:'Esporta in CSV',msg:'Mostra messaggio'},st=a=>a.map(s=>`<li>${A[s.a]}: <i>${E(s.t)}</i></li>`).join('');
return `<h2>Macro</h2>
${db.macros.map((m,i)=>`<div class="card"><b>${E(m.name)}</b><ol>${st(m.steps)}</ol><div class="row"><button class="pri" onclick="runM(${i})">▶ Esegui</button><button class="x" onclick="db.macros.splice(${i},1);sv();draw()">Elimina</button></div></div>`).join('')}
<h3>Nuova macro</h3><div class="card"><div class="row"><input value="${E(S.mn)}" onchange="S.mn=this.value" placeholder="nome macro"></div><ol>${st(S.macro)}</ol>
<div class="row"><select id="ma">${Object.entries(A).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select><select id="mt">${Object.keys(db.tables).map(x=>`<option>${E(x)}</option>`).join('')}</select><input id="mx" placeholder="testo (solo per messaggio)"><button onclick="addStep()">+ Aggiungi passo</button><button class="pri" onclick="saveM()">Salva macro</button></div></div>`},
dati(){return `<h2>Importa / Esporta</h2>${tbSel()}<div class="row">${T()?`<button onclick="S.io=csv(S.t);draw()">Esporta «${E(S.t)}» in CSV</button>`:''}<button onclick="S.io=JSON.stringify(db,null,1);draw()">Esporta tutto il database (JSON)</button></div>
<textarea rows="12" spellcheck="false" oninput="S.io=this.value" placeholder="CSV / JSON">${E(S.io)}</textarea>
<div class="row"><input type="file" accept=".csv,.txt,.json" onchange="rd(this)"><input id="ni" placeholder="nome nuova tabella"><button class="pri" onclick="impCSV()">Importa CSV come tabella</button><button onclick="impJ()">Ripristina database da JSON</button></div>
`}
};
draw();
</script>
<script>
const UD={theme:'auto',ac:'',gl:100,bl:14,r:16,rb:1,den:'n',ff:'i',lines:1,orbs:1,anim:1,lint:100,tint:0,zebra:0,name:'Mini-Access'};
let U;try{U={...UD,...JSON.parse(DS.getItem('mui'))}}catch{U={...UD}}
const FF={i:'"Instrument Sans","Helvetica Neue","Segoe UI",system-ui,sans-serif',s:'system-ui,"Segoe UI",sans-serif',g:'Georgia,"Times New Roman",serif',m:'"SF Mono",Consolas,monospace'};
const DN={c:['.12rem','13px'],n:['.3rem','14px'],a:['.6rem','16px']};
const hx=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
function ap(){const R=document.documentElement,st=R.style,set=(k,v)=>v===''?st.removeProperty(k):st.setProperty(k,v);
U.theme=='auto'?R.removeAttribute('data-theme'):R.setAttribute('data-theme',U.theme);
if(U.ac){const[r,g,b]=hx(U.ac);set('--ac',U.ac);set('--on',(r*.3+g*.59+b*.11)>150?'#101012':'#fff')}else{set('--ac','');set('--on','')}
set('--ga',U.gl/100);set('--bl',U.bl+'px');set('--r',U.r+'px');set('--rb',U.rb?'999px':'8px');set('--pd',DN[U.den][0]);set('--fs',DN[U.den][1]);set('--ff',FF[U.ff]);
const bg=$('#bg'),sv=bg.querySelector('svg');sv.style.display=U.lines?'':'none';sv.style.opacity=U.lint/100;bg.classList.toggle('no-o',!U.orbs);
try{U.anim?sv.unpauseAnimations():sv.pauseAnimations()}catch{}
if(U.tint&&U.ac)bg.style.setProperty('--ink',hx(U.ac).join(','));else bg.style.removeProperty('--ink');
document.body.classList.toggle('zb',!!U.zebra);$('#appname').textContent=U.name||'Mini-Access';document.title=U.name||'Mini-Access'}
const UI={set(k,v){U[k]=v;try{DS.setItem('mui',JSON.stringify(U))}catch{}ap()},
all(k,v){UI.set(k,v);draw()},
pre(o){U={...UD,...o,name:U.name};UI.set('name',U.name);draw()}};
const PRE=[['Cristallo',{}],['Notte',{theme:'dark',bl:18}],['Carta',{theme:'light',bl:0,lines:0,orbs:0,r:6,rb:0}],['Aurora',{theme:'dark',ac:'#a855f7',tint:1,bl:22,r:24}]];
const SW=['','#5b5bd6','#0a84ff','#16a34a','#e11d48','#f59e0b','#a855f7'];
const ch=(k,v,l)=>`<button class="chip ${U[k]===v?'on':''}" onclick="UI.all('${k}',${typeof v=='string'?`'${v}'`:v})">${l}</button>`;
const rg=(l,k,a,b,u='')=>`<label class="fl"><span>${l}</span><span class="row" style="margin:0;flex-wrap:nowrap"><input type="range" min="${a}" max="${b}" value="${U[k]}" oninput="UI.set('${k}',+this.value);this.nextElementSibling.textContent=this.value+'${u}'"><b>${U[k]}${u}</b></span></label>`;
const tgl=(l,k)=>`<label class="fl"><span>${l}</span><input type="checkbox" ${U[k]?'checked':''} onchange="UI.all('${k}',this.checked?1:0)"></label>`;
V.aspetto=()=>`<h2>Aspetto</h2>
<div class="card"><h3 style="margin-top:0">Stili pronti</h3>${PRE.map((p,i)=>`<button class="chip" onclick="UI.pre(PRE[${i}][1])">${p[0]}</button>`).join('')}</div>
<div class="grid"><div class="card"><h3 style="margin-top:0">Colori</h3><div class="row">${ch('theme','auto','Automatico')}${ch('theme','light','Chiaro')}${ch('theme','dark','Scuro')}</div>
<div class="row">${SW.map(c=>`<button class="sw ${U.ac==c?'on':''}" style="background:${c||'linear-gradient(135deg,#101012 50%,#fff 50%)'}" aria-label="Accento ${c||'monocromatico'}" onclick="UI.all('ac','${c}')"></button>`).join('')}</div>
<label class="fl"><span>Accento libero</span><input type="color" value="${U.ac||'#101012'}" onchange="UI.all('ac',this.value)"></label>${tgl('Sfondo nel colore accento','tint')}</div>
<div class="card"><h3 style="margin-top:0">Vetro</h3>${rg('Trasparenza','gl',0,150,'%')}${rg('Sfocatura','bl',0,40,'px')}${rg('Angoli','r',0,32,'px')}<div class="row">${ch('rb',1,'Pulsanti tondi')}${ch('rb',0,'Pulsanti squadrati')}</div></div>
<div class="card"><h3 style="margin-top:0">Testo e spazi</h3><div class="row">${ch('ff','i','Moderno')}${ch('ff','s','Sistema')}${ch('ff','g','Serif')}${ch('ff','m','Mono')}</div><div class="row">${ch('den','c','Compatta')}${ch('den','n','Normale')}${ch('den','a','Ampia')}</div>${tgl('Righe alternate nelle tabelle','zebra')}
<label class="fl"><span>Nome app</span><input value="${E(U.name)}" oninput="UI.set('name',this.value)"></label></div>
<div class="card"><h3 style="margin-top:0">Sfondo</h3>${tgl('Linee fluide','lines')}${rg('Intensità linee','lint',10,100,'%')}${tgl('Aloni','orbs')}${tgl('Movimento','anim')}</div></div>
<div class="row"><button class="x" onclick="UI.pre({})">Ripristina aspetto</button></div>`;
TABS.push(['aspetto','Aspetto']);ap();draw();
</script>
<script>
const AC={tab:['Apri tabella','t'],maschera:['Apri maschera','t'],report:['Apri report','t'],query:['Apri query','t'],macro:['Esegui macro','m'],csv:['Esporta in CSV','t'],nuova:['Nuovo record in','t'],sez:['Vai a','s'],msg:['Mostra messaggio','x']};
const GL=['▦','◫','☰','⌕','▶','⇩','＋','◐','✦','★','⚑','⌘','♥','☀'];
const tOk=k=>{const d=AC[k.a];if(!d)return false;return d[1]=='t'?!!db.tables[k.x]:d[1]=='m'?db.macros.some(m=>m.name==k.x):d[1]=='s'?TABS.some(([a])=>a==k.x):true};
const tdef=a=>{const d=AC[a][1];return d=='t'?Object.keys(db.tables)[0]:d=='m'?(db.macros[0]||{}).name||'':d=='s'?'tabelle':'Operazione completata'};
function tR(k){if(!tOk(k))return M('Destinazione non trovata: '+(k.x||'—'));const x=k.x;
switch(k.a){case'tab':S.t=x;S.rec=0;return go('tabelle');case'maschera':S.t=x;S.rec=0;return go('maschere');
case'report':S.t=x;S.rp={...S.rp,...rpDef(x)};return go('report');case'query':S.t=x;S.q=qd(x);return go('query');
case'macro':return runM(db.macros.findIndex(m=>m.name==x));case'csv':S.t=x;S.io=csv(x);M('Esportata «'+x+'» in CSV',1);return go('dati');
case'nuova':S.t=x;T().r.push(blank(x));S.rec=T().r.length-1;sv();return go('maschere');case'sez':return go(x);case'msg':return M(x,1)}}
function tsub(k){if(!tOk(k))return['Destinazione non disponibile',0];const[l,d]=AC[k.a];let e='';
if(['tab','maschera','nuova','report','query'].includes(k.a))e=' · '+T(k.x).r.length+' record';
else if(k.a=='macro')e=' · '+db.macros.find(m=>m.name==k.x).steps.length+' passi';else if(k.a=='sez')e=' '+TABS.find(([a])=>a==k.x)[1];
return[l+e,1]}
function tMv(a,b){if(a==null||b<0||b>=db.tiles.length||a==b)return;db.tiles.splice(b,0,db.tiles.splice(a,1)[0]);sv();draw()}
function tEd(i){S.ed=i;S.tf=i<0?{t:'',i:'▦',a:'tab',x:tdef('tab'),w:1}:{...db.tiles[i]};draw()}
function tF(k,v){S.tf[k]=v;if(k=='a')S.tf.x=tdef(v);draw()}
function tSave(){const k=S.tf;if(!k.t.trim())return M('Dai un titolo alla casella');if(!tOk(k))return M('Scegli una destinazione valida');k.t=k.t.trim();S.ed<0?db.tiles.push(k):db.tiles[S.ed]=k;S.ed=null;sv();draw()}
function tDel(i){if(!confirm('Eliminare questa casella?'))return;db.tiles.splice(i,1);S.ed=null;sv();draw()}
function cmds(){const o=[];for(const a in AC){const d=AC[a][1];if(d=='t')Object.keys(db.tables).forEach(x=>o.push({a,x,l:AC[a][0]+' '+x}));else if(d=='m')db.macros.forEach(m=>o.push({a,x:m.name,l:AC[a][0]+' '+m.name}));else if(d=='s')TABS.forEach(([k,n])=>o.push({a,x:k,l:AC[a][0]+' '+n}))}return o}
function cbF(v){const w=v.trim().toLowerCase().split(/\s+/).filter(Boolean);S.cm=w.length?cmds().filter(c=>w.every(x=>c.l.toLowerCase().includes(x))).slice(0,8):[];
$('#cl').innerHTML=S.cm.map((c,i)=>`<button onclick="tR(S.cm[${i}])">${E(c.l)}</button>`).join('')||(w.length?'<span class="mu">Nessun comando trovato</span>':'')}
function tForm(){const k=S.tf,d=AC[k.a][1];let tg;
if(d=='t'&&!Object.keys(db.tables).length)tg='<span class="mu">Nessuna tabella: creane una nella sezione Tabelle</span>';else if(d=='t')tg=`<select onchange="S.tf.x=this.value">${Object.keys(db.tables).map(x=>`<option ${x==k.x?'selected':''}>${E(x)}</option>`).join('')}</select>`;
else if(d=='m')tg=db.macros.length?`<select onchange="S.tf.x=this.value">${db.macros.map(m=>`<option ${m.name==k.x?'selected':''}>${E(m.name)}</option>`).join('')}</select>`:'<span class="mu">Nessuna macro: creane una nella sezione Macro</span>';
else if(d=='s')tg=`<select onchange="S.tf.x=this.value">${TABS.map(([a,n])=>`<option value="${a}" ${a==k.x?'selected':''}>${E(n)}</option>`).join('')}</select>`;
else tg=`<input value="${E(k.x)}" oninput="S.tf.x=this.value">`;
return `<div class="card"><h3 style="margin-top:0">${S.ed<0?'Nuova casella':'Modifica casella'}</h3>
<label class="fl"><span>Titolo</span><input value="${E(k.t)}" oninput="S.tf.t=this.value" placeholder="es. Ordini di oggi"></label>
<div class="fl"><span>Icona</span><div class="row" style="margin:0"><input value="${E(k.i)}" maxlength="4" style="width:4rem" oninput="S.tf.i=this.value">${GL.map(g=>`<button class="chip ${g==k.i?'on':''}" style="margin:0" onclick="tF('i','${g}')">${g}</button>`).join('')}</div></div>
<label class="fl"><span>Comando</span><select onchange="tF('a',this.value)">${Object.entries(AC).map(([a,v])=>`<option value="${a}" ${a==k.a?'selected':''}>${v[0]}</option>`).join('')}</select></label>
<label class="fl"><span>Destinazione</span>${tg}</label>
<div class="fl"><span>Dimensione</span><div class="row" style="margin:0"><button class="chip ${k.w!=2?'on':''}" style="margin:0" onclick="tF('w',1)">Normale</button><button class="chip ${k.w==2?'on':''}" style="margin:0" onclick="tF('w',2)">Larga</button></div></div>
<div class="row"><button class="pri" onclick="tSave()">Salva</button><button onclick="S.ed=null;draw()">Annulla</button>${S.ed>=0?`<button class="x" onclick="tDel(${S.ed})">Elimina</button>`:''}</div></div>`}
V.home=()=>{db.tiles??=[];if(S.ed>=db.tiles.length)S.ed=null;
return `<h2>Inizio</h2><div class="row"><input id="cb" class="cb" placeholder="Comando…  (Ctrl+K)" autocomplete="off" oninput="cbF(this.value)" onkeydown="if(event.key=='Enter'&&S.cm&&S.cm[0])tR(S.cm[0])"></div><div class="row" id="cl" style="margin-top:0"></div>
<div class="row"><h3 style="margin:0">Le tue caselle</h3><span style="flex:1"></span>${S.em?'<button onclick="tEd(-1)">+ Nuova casella</button>':''}<button class="chip ${S.em?'on':''}" style="margin:0" onclick="S.em=!S.em;S.ed=null;draw()">${S.em?'Fine modifica':'Modifica caselle'}</button></div>
${S.ed!=null?tForm():''}
<div class="tiles">${db.tiles.map((k,i)=>{const[sb,ok]=tsub(k);return `<div class="tile ${k.w==2?'w2':''} ${S.em?'em':''}" ${S.em?`draggable="true" ondragstart="S.dg=${i}" ondragover="event.preventDefault()" ondrop="tMv(S.dg,${i})"`:''}><button class="tm" onclick="${S.em?`tEd(${i})`:`tR(db.tiles[${i}])`}"><span class="ti">${E(k.i)}</span><span><b>${E(k.t)}</b><br><small class="${ok?'':'er'}">${E(sb)}</small></span></button>${S.em?`<span class="tc"><button onclick="tMv(${i},${i-1})" aria-label="Sposta prima">◀</button><button onclick="tMv(${i},${i+1})" aria-label="Sposta dopo">▶</button><button class="x" onclick="tDel(${i})" aria-label="Elimina casella">✕</button></span>`:''}</div>`}).join('')||'<div class="card" style="grid-column:1/-1"><button class="pri" onclick="S.em=true;tEd(-1)">+ Crea la prima casella</button></div>'}</div>
`};
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key=='k'){e.preventDefault();if(S.tab!='home')go('home');$('#cb').focus()}});
TABS.unshift(['home','Inizio']);S.tab='home';draw();
</script>
<script>if(matchMedia("(prefers-reduced-motion:reduce)").matches)document.querySelectorAll("#bg animate").forEach(a=>a.remove())</script>
<script>
/* ===== Toolbar, Note, Ricerca, Traduzione, LED ===== */
UD.led=0;UD.lo=100;UD.lang='it';U.led??=0;U.lo??=100;U.lang??='it';
const _ap=ap;ap=function(){_ap();const R=document.documentElement;R.classList.toggle('noled',!U.led);R.style.setProperty('--lo',U.lo/100)};
const IC={pen:'<path d="M4 20h4L19 9l-4-4L4 16z"/>',grid:'<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',list:'<path d="M4 7h16M4 12h16M4 17h10"/>',share:'<path d="M12 15V4M8 8l4-4 4 4M5 12v7h14v-7"/>',bm:'<path d="M7 4h10v16l-5-4-5 4z"/>',ct:'<circle cx="12" cy="12" r="8"/><path d="M12 4v16a8 8 0 0 0 0-16z" fill="currentColor"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',ul:'<path d="M9 7h11M9 12h11M9 17h11M4.5 7h.01M4.5 12h.01M4.5 17h.01"/>',al:'<path d="M4 6h16M4 10h10M4 14h16M4 18h10"/>',ac:'<path d="M4 6h16M7 10h10M4 14h16M7 18h10"/>',ar:'<path d="M4 6h16M10 10h10M4 14h16M10 18h10"/>',aj:'<path d="M4 6h16M4 10h16M4 14h16M4 18h16"/>'};
const ib=(i,f,c='',t='')=>`<button class="ib ${c}" title="${t}" aria-label="${t}" onmousedown="event.preventDefault()" onclick="${f}"><svg viewBox="0 0 24 24">${IC[i]}</svg></button>`;
const LN={it:'Italiano',en:'English',es:'Español',fr:'Français',de:'Deutsch'};
$('main').insertAdjacentHTML('afterbegin',`<div class="tbar">${ib('pen','tbNew()','','Nuovo record')}<select id="ts" class="ts" aria-label="Tabella attiva" onchange="tsw(this.value)"></select><input id="sq" class="sch" placeholder="Ricerca" autocomplete="off" oninput="tbQ(this.value)"><div class="seg">${ib('grid',"go('home')",'c1','Inizio')}${ib('list',"go('tabelle')",'c2','Tabelle')}</div>${ib('share',"S.io=JSON.stringify(db,null,1);go('dati')",'','Esporta database')}${ib('bm','tbBm()','c3','Aggiungi a Inizio')}${ib('ct','tbTh()','','Chiaro / scuro')}<select id="lg" aria-label="Lingua" onchange="UI.set('lang',this.value);draw()">${Object.entries(LN).map(([k,v])=>`<option value="${k}" ${k==U.lang?'selected':''}>${v}</option>`).join('')}</select>${ib('info',"M('Ctrl+K apre i comandi · il segnalibro aggiunge la sezione a Inizio · Note ha la traduzione automatica',1)",'c5','Informazioni')}</div>`);
function tbNew(){if(!T())return M('Crea prima una tabella');T().r.push(blank(S.t));S.rec=T().r.length-1;sv();go('maschere')}
function tbQ(v){S.sq=v;if(v.trim()){S.tab='cerca';draw()}}
function tbBm(){const t=TABS.find(x=>x[0]==S.tab);if(!t||['home','cerca'].includes(S.tab))return M('Apri una sezione da aggiungere a Inizio');db.tiles??=[];if(db.tiles.some(k=>k.a=='sez'&&k.x==S.tab))return M('Già presente in Inizio');db.tiles.push({t:t[1],i:'★',a:'sez',x:S.tab,w:1});sv();M('Aggiunta a Inizio',1)}
function tbTh(){const d=(document.documentElement.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'))=='dark';UI.all('theme',d?'light':'dark')}
V.cerca=()=>{const q=(S.sq||'').trim().toLowerCase(),o=[];if(q)for(const tb in db.tables)db.tables[tb].r.forEach((r,i)=>db.tables[tb].f.forEach(f=>{const v=String(disp(tb,f.n,r[f.n]));if(v.toLowerCase().includes(q)&&o.length<60)o.push([tb,i,f.n,v])}));
return `<h2>Ricerca</h2><p class="mu">${o.length} risultati per «${E(S.sq)}»</p><ul class="rl">${o.map(([tb,i,f,v])=>`<li><b>${E(tb)}</b><span>${E(f)}: ${E(v)}</span><button onclick="S.t='${tb}';S.rec=${i};go('maschere')">Apri</button></li>`).join('')||'<li class="mu">Nessun risultato</li>'}</ul>`};
/* Note con barra di formattazione */
let R0;document.addEventListener('selectionchange',()=>{const s=getSelection(),e=$('#ed');if(e&&s.rangeCount&&e.contains(s.anchorNode))R0=s.getRangeAt(0)});
function ex(c,v){const e=$('#ed');e.focus();if(R0){const s=getSelection();s.removeAllRanges();s.addRange(R0)}document.execCommand(c,false,v);ns()}
function ns(){try{DS.setItem('mnote',$('#ed').innerHTML)}catch{}}
function fsz(px){ex('fontSize',7);$('#ed').querySelectorAll('font[size="7"]').forEach(f=>{const s=document.createElement('span');s.style.fontSize=px+'px';s.innerHTML=f.innerHTML;f.replaceWith(s)});ns()}
const op=(a,s)=>a.map(x=>`<option ${x==s?'selected':''}>${x}</option>`).join('');
V.note=()=>{let h='';try{h=DS.getItem('mnote')||''}catch{}setTimeout(()=>{const e=$('#ed');if(e&&!e.dataset.i){e.dataset.i=1;e.innerHTML=h||'<div><br></div>'}});
return `<h2>Note</h2><div class="fbar"><select onchange="ex('formatBlock',this.value)" aria-label="Stile"><option value="div">Normale</option><option value="h1">Titolo</option><option value="h3">Sottotitolo</option><option value="blockquote">Citazione</option></select>
<select onchange="ex('fontName',this.value)" aria-label="Carattere">${op(['Palatino','Georgia','Helvetica','Courier New'])}</select><select onchange="fsz(this.value)" aria-label="Dimensione">${op([11,13,15,18,22,28],15)}</select><span class="sp"></span>
${ib('pen',"ex('bold')",'','Grassetto').replace('<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>','<b>B</b>')}${ib('pen',"ex('italic')",'','Corsivo').replace(/<svg.*<\/svg>/,'<i>I</i>')}${ib('pen',"ex('underline')",'','Sottolineato').replace(/<svg.*<\/svg>/,'<u>U</u>')}<span class="sp"></span>
${ib('al',"ex('justifyLeft')",'','Sinistra')}${ib('ac',"ex('justifyCenter')",'','Centro')}${ib('ar',"ex('justifyRight')",'','Destra')}${ib('aj',"ex('justifyFull')",'','Giustificato')}<span class="sp"></span>
<select onchange="$('#ed').style.lineHeight=this.value;" aria-label="Interlinea">${op([1,1.1,1.3,1.5,2],1.5)}</select>${ib('ul',"ex('insertUnorderedList')",'','Elenco')}</div>
<div id="ed" class="paper ed" contenteditable="true" spellcheck="true" oninput="ns()"></div>
<div class="row"><select id="tl">${[['en','English'],['es','Español'],['fr','Français'],['de','Deutsch'],['pt','Português'],['ru','Русский'],['zh','中文'],['ja','日本語'],['ar','العربية']].map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select><button class="pri" onclick="trNote()">Traduci</button><button onclick="trBack()">Ripristina originale</button></div>
`};
let ORIG;
async function trNote(){const e=$('#ed'),l=$('#tl').value,ls=e.innerText.split('\n').filter(x=>x.trim());if(!ls.length)return M('Scrivi qualcosa da tradurre');ORIG=ORIG||e.innerHTML;M('Traduzione in corso…',1);
try{const o=[];for(const s of ls){const r=await fetch('https://api.mymemory.translated.net/get?q='+encodeURIComponent(s.slice(0,480))+'&langpair=it|'+l);const j=await r.json();o.push(j.responseData.translatedText)}
e.innerHTML=o.map(x=>`<div>${E(x)}</div>`).join('');ns();M('Tradotto',1)}catch{M('Traduzione non disponibile: controlla la connessione o apri il file in locale')}}
function trBack(){if(!ORIG)return M('Niente da ripristinare');$('#ed').innerHTML=ORIG;ORIG=null;ns()}
/* Traduzione interfaccia (offline) */
const LG=['it','en','es','fr','de'],TR=`Inizio|Home|Inicio|Accueil|Start
Tabelle|Tables|Tablas|Tables|Tabellen
Relazioni|Relationships|Relaciones|Relations|Beziehungen
Query|Queries|Consultas|Requêtes|Abfragen
Maschere|Forms|Formularios|Formulaires|Formulare
Report|Reports|Informes|Rapports|Berichte
Macro|Macros|Macros|Macros|Makros
Importa / Esporta|Import / Export|Importar / Exportar|Importer / Exporter|Import / Export
Aspetto|Appearance|Aspecto|Apparence|Aussehen
Note|Notes|Notas|Notes|Notizen
Dati|Data|Datos|Données|Daten
Output|Output|Salida|Sortie|Ausgabe
Impostazioni|Settings|Ajustes|Réglages|Einstellungen
Ripristina dati di esempio|Restore sample data|Restaurar datos de ejemplo|Restaurer les données d’exemple|Beispieldaten wiederherstellen
+ Nuova riga|+ New row|+ Nueva fila|+ Nouvelle ligne|+ Neue Zeile
Aggiungi campo|Add field|Añadir campo|Ajouter un champ|Feld hinzufügen
Crea tabella|Create table|Crear tabla|Créer la table|Tabelle erstellen
Struttura della tabella|Table structure|Estructura de la tabla|Structure de la table|Tabellenstruktur
Salva|Save|Guardar|Enregistrer|Speichern
Elimina|Delete|Eliminar|Supprimer|Löschen
Annulla|Cancel|Cancelar|Annuler|Abbrechen
+ Nuovo|+ New|+ Nuevo|+ Nouveau|+ Neu
Crea relazione|Create relationship|Crear relación|Créer la relation|Beziehung erstellen
Nessuna relazione|No relationships|Sin relaciones|Aucune relation|Keine Beziehungen
Le tue caselle|Your tiles|Tus casillas|Vos cases|Deine Kacheln
Modifica caselle|Edit tiles|Editar casillas|Modifier les cases|Kacheln bearbeiten
Fine modifica|Done editing|Terminar edición|Terminer|Fertig
Stampa / salva PDF|Print / save PDF|Imprimir / guardar PDF|Imprimer / PDF|Drucken / PDF
Nuova macro|New macro|Nueva macro|Nouvelle macro|Neues Makro
Nessuna tabella|No tables|Sin tablas|Aucune table|Keine Tabellen
Ricerca|Search|Buscar|Rechercher|Suche
Stili pronti|Presets|Estilos listos|Styles prédéfinis|Vorlagen
Colori|Colors|Colores|Couleurs|Farben
Contorni LED|LED outlines|Contornos LED|Contours LED|LED-Konturen
Traduci|Translate|Traducir|Traduire|Übersetzen
Ripristina originale|Restore original|Restaurar original|Restaurer l’original|Original wiederherstellen`.split('\n').map(r=>r.split('|'));
function trUI(){const i=Math.max(0,LG.indexOf(U.lang)),w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),L=[];let n;while(n=w.nextNode())L.push(n);
L.forEach(n=>{const p=n.parentNode;if(p.closest('script,style,option,#ed,textarea'))return;const o=n._o??=n.nodeValue,k=o.trim(),r=TR.find(x=>x[0]==k);n.nodeValue=r?o.replace(k,r[i]):o});
const s=$('#sq');if(s)s.placeholder=TR.find(x=>x[0]=='Ricerca')[i];document.documentElement.lang=LG[i]}
function tsw(n){S.t=n;S.rec=0;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};if(!['tabelle','maschere','query','report','dati'].includes(S.tab))S.tab='tabelle';draw()}
function tsr(){const e=$('#ts'),k=Object.keys(db.tables);if(!e)return;e.style.display=k.length?'':'none';e.innerHTML=k.map(n=>`<option ${n==S.t?'selected':''}>${E(n)}</option>`).join('')}
document.addEventListener('keydown',e=>{if(e.altKey&&(e.key=='ArrowUp'||e.key=='ArrowDown')){const k=Object.keys(db.tables);if(!k.length)return;e.preventDefault();tsw(k[(k.indexOf(S.t)+(e.key=='ArrowDown'?1:k.length-1))%k.length])}});
const _dr=draw;draw=function(){_dr();tsr();trUI()};
const _va=V.aspetto;V.aspetto=()=>_va()+`<div class="card"><h3 style="margin-top:0">Contorni LED</h3>${tgl('Contorni LED','led')}${rg('Intensità','lo',0,100,'%')}</div>`;
ap();draw();
</script>
<script>
/* ===== v3: annulla, tabelle potenziate, guida, barra semplificata ===== */
UD.guide=0;U.guide=0;S.tq='';S.so=null;S.dt=0;
function undo(){if(!HS.length)return M('Niente da annullare');HL=HS.pop();db=JSON.parse(HL);try{DS.setItem('mdb',HL)}catch{}if(!T())S.t=Object.keys(db.tables)[0];M('Ultima modifica annullata',1);draw()}
document.addEventListener('keydown',e=>{const t=e.target;if((e.ctrlKey||e.metaKey)&&!e.shiftKey&&e.key=='z'&&!['INPUT','TEXTAREA','SELECT'].includes(t.tagName)&&!t.isContentEditable){e.preventDefault();undo()}
if(e.key=='Enter'&&t.matches&&t.matches('.tbl td input[data-f]:not([type=checkbox])')){const td=t.closest('td'),tr=td.parentNode,x=[...tr.children].indexOf(td)+1,p=[...tr.parentNode.children].indexOf(tr)+1;t.blur();setTimeout(()=>{const n=document.querySelector(`.tbl tr:nth-child(${p+1}) td:nth-child(${x}) input`);n&&n.focus()})}});
function sortT(c){S.so=S.so&&S.so.c==c?(S.so.d==1?{c,d:-1}:null):{c,d:1};draw()}
function dupRow(i){const o={...T().r[i]};if(o.id!==undefined)o.id=Math.max(0,...T().r.map(r=>+r.id||0))+1;T().r.splice(i+1,0,o);sv();draw()}
function renF(o,v){v=nm(v);const t=T();if(!v||v==o)return draw();if(fld(S.t,v)){M('Nome già usato');return draw()}const f=fld(S.t,o);f.n=v;t.r.forEach(r=>{r[v]=r[o];delete r[o]});db.rel.forEach(r=>['a','b'].forEach(k=>{if(r[k]==S.t+'.'+o)r[k]=S.t+'.'+v}));sv();draw()}
function reqF(n,c){const f=fld(S.t,n);if(c)f.q=1;else delete f.q;sv();draw()}
function typF(n,ty){const f=fld(S.t,n),t=T(),old=f.t;if(old==ty)return;const nr=[];try{t.r.forEach(r=>{const v=old=='sì/no'?(r[n]?'sì':'no'):r[n];nr.push(ty=='sì/no'?(v===true||v=='sì'||v=='true'):cast({...f,t:ty,q:0},v))})}catch(e){M('Conversione impossibile: '+e);return draw()}t.r.forEach((r,i)=>r[n]=nr[i]);f.t=ty;sv();draw()}
function delF(n){if(n=='id')return M('Il campo id non si può eliminare');if(db.rel.some(r=>r.a==S.t+'.'+n||r.b==S.t+'.'+n))return M('Il campo è usato in una relazione: eliminala prima');if(!confirm('Eliminare il campo «'+n+'» e i suoi dati?'))return;const t=T();t.f=t.f.filter(f=>f.n!=n);t.r.forEach(r=>delete r[n]);sv();draw()}
function renT(v){v=nm(v);const o=S.t;if(!v||v==o)return draw();if(db.tables[v]){M('Nome già usato');return draw()}const nt={};for(const k in db.tables)nt[k==o?v:k]=db.tables[k];db.tables=nt;const re=x=>x.startsWith(o+'.')?v+x.slice(o.length):x;db.rel.forEach(r=>{r.a=re(r.a);r.b=re(r.b)});(db.tiles||[]).forEach(k=>{if(k.x==o&&['tab','maschera','report','query','csv','nuova'].includes(k.a))k.x=v});db.macros.forEach(m=>m.steps.forEach(s=>{if(s.a!='msg'&&s.t==o)s.t=v}));S.t=v;S.q=qd(v);S.rp={...S.rp,...rpDef(v)};sv();draw()}
function newT(){const n=nm(prompt('Nome della nuova tabella')||'');if(!n)return;if(db.tables[n])return M('Nome già usato');db.tables[n]={f:[{n:'id',t:'numero',q:1},{n:'nome',t:'testo'}],r:[]};S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};sv();draw()}
/* ===== v4: tabelle potenziate ===== */
const TL=['testo','numero','valuta','data','sì/no','scelta','link'];
const eur=x=>x.toLocaleString('it-IT',{style:'currency',currency:'EUR'});
const _c=cast;cast=function(f,v){if(f.t=='scelta'||f.t=='link'){v=String(v).trim();if(v===''){if(f.q)throw `«${f.n}» è obbligatorio`;return ''}if(f.t=='link'&&!/^(https?:\/\/|www\.)\S+$/i.test(v))throw `«${f.n}» deve essere un link`;return v}return _c(f,v)};
const _tf=typF;typF=function(n,ty){const f=fld(S.t,n);if(ty=='valuta'){if(f.t!='numero')_tf(n,'numero');if(f.t=='numero'){f.cur=1;sv()}return draw()}
if(f.cur&&ty=='numero'){delete f.cur;sv();return draw()}delete f.cur;_tf(n,ty);if(ty=='scelta'&&f.t=='scelta'&&!f.o){f.o=[...new Set(T().r.map(r=>r[n]).filter(x=>x!==''))];sv();draw()}};
const _af=addF;addF=function(){const n=nm($('#nf').value),v=$('#nt').value;if(v=='valuta')$('#nt').value='numero';_af();const f=fld(S.t,n);if(v=='valuta'&&f&&f.t=='numero'){f.cur=1;sv();draw()}};
const _dl=del;del=function(i){S.sel=[];_dl(i)};const _dp=dupRow;dupRow=function(i){S.sel=[];_dp(i)};
function setOpt(n,v){fld(S.t,n).o=v.split(',').map(x=>x.trim()).filter(Boolean);sv();draw()}
function hideF(n){const f=fld(S.t,n);if(f.h)delete f.h;else f.h=1;sv();draw()}
function moveF(n,d){const t=T(),i=t.f.findIndex(f=>f.n==n),j=i+d;if(j<0||j>=t.f.length)return;[t.f[i],t.f[j]]=[t.f[j],t.f[i]];sv();draw()}
function selR(i,c){S.sel=c?[...new Set([...S.sel,i])]:S.sel.filter(x=>x!=i);draw()}
function selAll(c){S.sel=c?[...(S.vis||[])]:[];draw()}
function delSel(){const t=T(),ix=[...S.sel].sort((a,b)=>b-a),ok=ix.filter(i=>!used(S.t,t.r[i]));if(!ok.length)return M('Righe collegate ad altre tabelle');if(!confirm('Eliminare '+ok.length+' righe?'))return;ok.forEach(i=>t.r.splice(i,1));S.sel=[];sv();draw();if(ok.length<ix.length)M('Alcune righe sono collegate e non sono state eliminate')}
function csvT(){const t=T(),f=t.f.filter(f=>!f.h),q=x=>`"${String(fmt(x)).replace(/"/g,'""')}"`,rr=(S.vis||t.r.map((r,i)=>i)).map(i=>t.r[i]),c=[f.map(g=>q(g.n)).join(';'),...rr.map(r=>f.map(g=>q(g.t=='numero'||g.t=='calcolo'?String(r[g.n]).replace('.',','):disp(S.t,g.n,r[g.n]))).join(';'))].join('\n');try{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+c],{type:'text/csv'}));a.download=S.t+'.csv';a.click();M('CSV scaricato',1)}catch{S.io=c;go('dati')}}
document.addEventListener('keydown',e=>{const t=e.target;if(!t.matches)return;if((e.key=='ArrowDown'||e.key=='ArrowUp')&&t.matches('.tbl td input[data-f]:not([type=checkbox]):not([type=date])')){const td=t.closest('td'),tr=td.parentNode,x=[...tr.children].indexOf(td)+1,p=[...tr.parentNode.children].indexOf(tr)+1+(e.key=='ArrowDown'?1:-1),n=document.querySelector(`.tbl tr:nth-child(${p}) td:nth-child(${x}) input`);if(n){e.preventDefault();n.focus();n.select&&n.select()}}
if(e.ctrlKey&&e.key=='Enter'&&t.closest('.tbl'))addRow()});
S.sel=[];S.selT=S.t;
const EYE='<svg viewBox="0 0 24 24"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
/* ===== v5: grandi quantità di dati ===== */
S.pg=0;S.ps=100;S.cf={};TL.push('calcolo');
const nrm=x=>String(x??'').trim();
const pn=v=>+String(v).replace(/[€\s]/g,'').replace(/\.(?=\d{3}(\D|$))/g,'').replace(',','.');
const isD=v=>/^\d{4}-\d\d-\d\d$|^\d{1,2}[\/.-]\d{1,2}[\/.-]\d{4}$/.test(v);
function parseTbl(t){const d=t.includes('\t')?'\t':((t.match(/;/g)||[]).length>=(t.match(/,/g)||[]).length?';':','),R=[];let r=[],c='',q=0;for(let i=0;i<t.length;i++){const h=t[i];if(q){if(h=='"'){if(t[i+1]=='"'){c+='"';i++}else q=0}else c+=h}else if(h=='"'&&c==='')q=1;else if(h==d){r.push(c);c=''}else if(h=='\n'||h=='\r'){if(h=='\r'&&t[i+1]=='\n')i++;r.push(c);R.push(r);r=[];c=''}else c+=h}if(c!==''||r.length){r.push(c);R.push(r)}return R.filter(r=>r.some(x=>nrm(x)!==''))}
function dty(c){c=c.map(nrm).filter(Boolean);if(!c.length)return 'testo';if(c.every(v=>!/^0\d/.test(v)&&v.length<=15&&!isNaN(pn(v))))return 'numero';if(c.every(isD))return 'data';return 'testo'}
function cz(f,v,bad){v=nrm(v);if(f.t=='sì/no')return /^(true|vero|sì|si|yes|1|x)$/i.test(v);if(v==='')return '';const k=fk(S.t,f.n);if(k){const rr=T(k[0]).r.find(r=>String(lab(k[0],r)).toLowerCase()==v.toLowerCase()||String(r[k[1]])==v);if(rr)return rr[k[1]];bad.n++;return ''}
if(f.t=='numero'){const n=pn(v);if(isNaN(n)){bad.n++;return ''}return n}
if(f.t=='data'){const m=v.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/);if(m)return `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;if(/^\d{4}-\d\d-\d\d$/.test(v))return v;bad.n++;return ''}
if(f.t=='scelta'){f.o=f.o||[];if(!f.o.includes(v))f.o.push(v)}return v}
function cmp(f,v,q){q=q.trim();if(!q)return true;const s=String(disp(S.t,f.n,v)).toLowerCase(),n=pn(v),m=q.match(/^(>=|<=|>|<|=|!)\s*(.*)$/);if(m){const x=m[2].toLowerCase(),xn=pn(x),u=!isNaN(n)&&!isNaN(xn)&&nrm(v)!==''&&x!=='',a=u?n:s,b=u?xn:x;return m[1]=='>'?a>b:m[1]=='<'?a<b:m[1]=='>='?a>=b:m[1]=='<='?a<=b:m[1]=='='?String(a)==String(b):!s.includes(x)}return s.includes(q.toLowerCase())}
function cfSet(n,v){S.cf[n]=v;S.pg=0;draw();const e=document.querySelector(`.fr input[data-c="${n}"]`);if(e){e.focus();e.setSelectionRange(99,99)}}
function pgGo(d){S.pg=Math.max(0,S.pg+d);draw()}function psSet(v){S.ps=+v;S.pg=0;draw()}
const scope=()=>S.sel.length?[...S.sel]:[...(S.vis||[])];
function dlg(h){let d=$('#dg');if(!d){d=document.createElement('dialog');d.id='dg';document.body.appendChild(d)}d.innerHTML=`<div class="dgh"><button class="ib" aria-label="Chiudi" onclick="dgc()">✕</button></div>${h}`;d.showModal?d.showModal():d.setAttribute('open','')}
function dgc(){const d=$('#dg');if(d)d.close?d.close():d.removeAttribute('open')}
const colOpts=()=>T().f.filter(f=>f.n!='id'&&f.t!='calcolo').map(f=>`<option>${E(f.n)}</option>`).join('');
/* incolla / importa */
function pasteDlg(){dlg(`<h3>Incolla da Excel</h3><textarea id="pt" placeholder="Ctrl+V"></textarea><div class="row"><input type="file" accept=".csv,.tsv,.txt" onchange="fileTo(this)"><label><input type="checkbox" id="ph" checked> Prima riga = intestazioni</label></div><div class="row"><select id="pm"><option value="a">Aggiungi a «${E(S.t)}»</option><option value="n">Nuova tabella</option></select><input id="pn" placeholder="Nome nuova tabella" value="importata"><button class="pri" onclick="pasteGo()">Importa</button></div>`);setTimeout(()=>{const e=$('#pt');e&&e.focus()})}
function fileTo(i){const f=i.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{if(String(r.result).includes('\ufffd')){const r2=new FileReader();r2.onload=()=>$('#pt').value=r2.result;r2.readAsText(f,'windows-1252')}else $('#pt').value=r.result};r.readAsText(f)}
function pasteGo(){const R=parseTbl($('#pt').value);if(!R.length)return M('Niente da importare');const hd=$('#ph').checked,mode=$('#pm').value,bad={n:0},H=hd?R.shift().map(nrm):null;if(!R.length)return M('Nessuna riga dati');const W=R.reduce((m,r)=>Math.max(m,r.length),H?H.length:0),cols=Array.from({length:W},(_,j)=>R.map(r=>r[j]));
let names=Array.from({length:W},(_,j)=>nm(H&&H[j]||'')||'campo'+(j+1));names=names.map((n,j)=>names.indexOf(n)<j?n+'_'+(j+1):n);
if(mode=='n'){const n=nm($('#pn').value)||'importata';if(db.tables[n])return M('Esiste già una tabella con questo nome');const hasId=names.includes('id'),f=names.map((x,j)=>({n:x,t:x=='id'?'numero':dty(cols[j])}));if(!hasId)f.unshift({n:'id',t:'numero',q:1});let id=1;const r=R.map(row=>{const o={};if(!hasId)o.id=id++;names.forEach((x,j)=>{o[x]=cz(f.find(g=>g.n==x),row[j],bad)});return o});db.tables[n]={f,r};S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)}}
else{const t=T(),vfs=t.f.filter(f=>!f.h&&f.t!='calcolo'&&f.n!='id'),hasId=t.f.some(f=>f.n=='id'),fs=names.map((x,j)=>{let f=hd?t.f.find(g=>g.n.toLowerCase()==x.toLowerCase()):vfs[j];if(!f&&hd){f={n:x,t:dty(cols[j])};t.f.push(f);t.r.forEach(r=>r[x]=f.t=='sì/no'?false:'')}return f});let id=t.r.reduce((m,r)=>Math.max(m,+r.id||0),0)+1;
R.forEach(row=>{const o={};t.f.forEach(f=>o[f.n]=f.t=='sì/no'?false:'');if(hasId)o.id=id++;fs.forEach((f,j)=>{if(f&&f.t!='calcolo'&&f.n!='id')o[f.n]=cz(f,row[j],bad)});t.r.push(o)})}
S.sel=[];S.tq='';S.cf={};S.pg=0;sv();dgc();M(`Importate ${R.length} righe`+(bad.n?` · ${bad.n} valori non validi svuotati`:''),1);draw()}
document.addEventListener('paste',e=>{const t=e.target;if(!t.matches||!t.matches('.tbl td input[data-f]:not([type=checkbox])'))return;const txt=(e.clipboardData||window.clipboardData).getData('text');if(!/[\t\n]/.test(txt.replace(/\r?\n$/,'')))return;e.preventDefault();const R=parseTbl(txt),tb=T(),vfs=tb.f.filter(f=>!f.h&&f.t!='calcolo'),i0=+t.closest('tr').dataset.i,c0=vfs.findIndex(f=>f.n==t.dataset.f),bad={n:0},hasId=tb.f.some(f=>f.n=='id');let id=tb.r.reduce((m,r)=>Math.max(m,+r.id||0),0)+1;
R.forEach((row,k)=>{let o=tb.r[i0+k];if(!o){o={};tb.f.forEach(f=>o[f.n]=f.t=='sì/no'?false:'');if(hasId)o.id=id++;tb.r.push(o)}row.forEach((v,j)=>{const f=vfs[c0+j];if(f&&f.n!='id')o[f.n]=cz(f,v,bad)})});sv();M(`Incollate ${R.length} righe`+(bad.n?` · ${bad.n} non validi`:''),1);draw()});
/* copia, esporta */
function cp2(t,ok){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy');ok()}catch{M('Copia non riuscita')}a.remove()}
function copyT(){const t=T(),f=t.f.filter(f=>!f.h),ix=S.sel.length?[...S.sel].sort((a,b)=>a-b):(S.vis||t.r.map((_,i)=>i)),c=x=>String(fmt(x)).replace(/[\t\r\n]+/g,' '),tsv=[f.map(g=>g.n).join('\t'),...ix.map(i=>f.map(g=>c(disp(S.t,g.n,t.r[i][g.n]))).join('\t'))].join('\n'),ok=()=>M(`Copiate ${ix.length} righe: incolla in Excel`,1);navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(tsv).then(ok,()=>cp2(tsv,ok)):cp2(tsv,ok)}
function xlsT(){const t=T(),f=t.f.filter(f=>!f.h),rr=(S.vis||t.r.map((_,i)=>i)).map(i=>t.r[i]),h=`<html><head><meta charset="utf-8"></head><body><table><tr>${f.map(g=>`<th>${E(g.n)}</th>`).join('')}</tr>${rr.map(r=>`<tr>${f.map(g=>`<td>${E(g.t=='numero'||g.t=='calcolo'?String(r[g.n]).replace('.',','):disp(S.t,g.n,r[g.n]))}</td>`).join('')}</tr>`).join('')}</table></body></html>`;try{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([h],{type:'application/vnd.ms-excel'}));a.download=S.t+'.xls';a.click();M('Excel scaricato',1)}catch{M('Download non disponibile')}}
/* trova e sostituisci, imposta, duplicati, duplica tabella */
function frDlg(){dlg(`<h3>Trova e sostituisci</h3><div class="row"><select id="fc"><option value="">Tutte le colonne di testo</option>${colOpts()}</select><input id="ff" placeholder="Trova"><input id="fr" placeholder="Sostituisci con"></div><div class="row"><span class="mu">${scope().length} righe</span><span style="flex:1"></span><button class="pri" onclick="frGo()">Sostituisci</button></div>`)}
function frGo(){const a=nrm($('#ff').value),b=$('#fr').value,c=$('#fc').value;if(!a)return M('Scrivi cosa trovare');const t=T(),re=new RegExp(a.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),bad={n:0};let n=0;scope().forEach(i=>{const r=t.r[i];t.f.forEach(f=>{if(c?f.n!=c:!['testo','scelta','link'].includes(f.t))return;if(f.n=='id'||f.t=='calcolo'||f.t=='sì/no'||fk(S.t,f.n))return;const v=String(r[f.n]??'');re.lastIndex=0;if(re.test(v)){re.lastIndex=0;r[f.n]=cz(f,v.replace(re,b),bad);n++}})});sv();dgc();M(`${n} celle modificate`,n>0);draw()}
function setDlg(){dlg(`<h3>Imposta colonna</h3><div class="row"><select id="sc" onchange="setIn()">${colOpts()}</select><span id="si"></span><button class="pri" onclick="setGo()">Applica a ${scope().length} righe</button></div>`);setIn()}
function setIn(){const f=fld(S.t,$('#sc').value),k=fk(S.t,f.n);$('#si').innerHTML=f.t=='sì/no'?'<select id="sv"><option>sì</option><option>no</option></select>':(f.t=='scelta'||k)?`<select id="sv"><option value=""></option>${(k?T(k[0]).r.map(r=>`<option value="${E(r[k[1]])}">${E(lab(k[0],r))}</option>`):(f.o||[]).map(o=>`<option>${E(o)}</option>`)).join('')}</select>`:`<input id="sv" type="${f.t=='data'?'date':'text'}" placeholder="Valore">`}
function setGo(){const f=fld(S.t,$('#sc').value),v=$('#sv').value,t=T();let val;try{val=f.t=='sì/no'?v=='sì':cast(f,v)}catch(e){return M(e)}scope().forEach(i=>t.r[i][f.n]=val);sv();dgc();M('Fatto',1);draw()}
function dupDlg(){dlg(`<h3>Rimuovi duplicati</h3><div class="row">${T().f.filter(f=>f.n!='id'&&f.t!='calcolo').map((f,i)=>`<label><input type="checkbox" class="dk" value="${E(f.n)}" ${i==0?'checked':''}> ${E(f.n)}</label>`).join('')}</div><div class="row"><span style="flex:1"></span><button class="pri" onclick="dupGo()">Rimuovi</button></div>`)}
function dupGo(){const ks=[...document.querySelectorAll('.dk:checked')].map(x=>x.value),t=T();if(!ks.length)return M('Scegli almeno un campo');const seen=new Set(),dl=new Set();t.r.forEach((r,i)=>{const k=ks.map(n=>String(disp(S.t,n,r[n])).trim().toLowerCase()).join('\u0001');if(seen.has(k)){if(!used(S.t,r))dl.add(i)}else seen.add(k)});if(!dl.size){dgc();return M('Nessun duplicato')}if(!confirm('Eliminare '+dl.size+' righe duplicate?'))return;t.r=t.r.filter((_,i)=>!dl.has(i));S.sel=[];sv();dgc();M(`${dl.size} duplicati rimossi`,1);draw()}
function cloneT(){let n=S.t+'_copia',k=2;while(db.tables[n])n=S.t+'_copia'+k++;db.tables[n]=JSON.parse(JSON.stringify(T()));S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};sv();M('Tabella duplicata',1);draw()}
/* colonne calcolate */
function recalcAll(){for(const k in db.tables){const t=db.tables[k],cf=t.f.filter(f=>f.t=='calcolo'&&f.fx);if(!cf.length)continue;t.r.forEach(r=>cf.forEach(f=>{try{const e=f.fx.replace(/\{([^}]+)\}/g,(_,n)=>{const v=r[n],x=typeof v=='number'?v:pn(v);return isNaN(x)?0:x}),z=/^[\d+\-*\/().\s%]*$/.test(e)&&e.trim()?(new Function('return '+e))():NaN;r[f.n]=isFinite(z)?Math.round(z*1e4)/1e4:''}catch{r[f.n]=''}}))}}
function setFx(n,v){fld(S.t,n).fx=v;sv();draw()}
const _tf2=typF;typF=function(n,ty){_tf2(n,ty);const f=fld(S.t,n);if(ty=='calcolo'&&f&&f.t=='calcolo'&&f.fx===undefined){f.fx='';sv();draw()}};
const _ar=addRow;addRow=function(){S.tq='';S.so=null;S.cf={};_ar();const n=T().r.length;S.pg=Math.ceil(n/S.ps)-1;draw();setTimeout(()=>{const rs=document.querySelectorAll('.tbl tr[data-i]'),r=rs[rs.length-1],e=r&&(r.querySelector('td:nth-child(3) :is(input,select)')||r.querySelector('td:nth-child(2) :is(input,select)'));e&&e.focus()})};
V.tabelle=()=>{const t=T();if(!t)return `<h2>Tabelle</h2>${tbSel(1)}`;if(S.selT!=S.t){S.sel=[];S.cf={};S.pg=0;S.selT=S.t}
const q=S.tq.trim().toLowerCase(),so=S.so,vf=t.f.filter(f=>!f.h),cfs=Object.entries(S.cf).filter(([n,v])=>v&&fld(S.t,n));let rows=t.r.map((r,i)=>[r,i]);
if(q)rows=rows.filter(([r])=>t.f.some(f=>String(disp(S.t,f.n,r[f.n])).toLowerCase().includes(q)));
if(cfs.length)rows=rows.filter(([r])=>cfs.every(([n,v])=>cmp(fld(S.t,n),r[n],v)));
if(so&&fld(S.t,so.c))rows.sort((a,b)=>{const x=a[0][so.c],y=b[0][so.c];return(x>y?1:x<y?-1:0)*so.d});
S.vis=rows.map(x=>x[1]);const np=Math.max(1,Math.ceil(rows.length/S.ps));S.pg=Math.min(S.pg,np-1);const pr=rows.slice(S.pg*S.ps,(S.pg+1)*S.ps),sl=i=>S.sel.includes(i),all=rows.length&&rows.every(([,i])=>sl(i)),tot=vf.map(f=>(f.t=='numero'||f.t=='calcolo')&&f.n!='id'?rows.reduce((s,[r])=>s+(+r[f.n]||0),0):null);
return `<h2>Tabelle</h2>${tbSel(1)}
<div class="row"><input class="sch2" placeholder="Filtra" value="${E(S.tq)}" oninput="S.tq=this.value;S.pg=0;draw();const i=document.querySelector('.sch2');i.focus();i.setSelectionRange(99,99)">${S.sel.length?`<b>${S.sel.length} ✓</b><button class="x" title="Elimina selezionate" aria-label="Elimina selezionate" onclick="delSel()">✕</button>`:`<span class="mu">${rows.length}/${t.r.length}</span>`}
<details class="more tm"><summary>Strumenti</summary><div class="mm">${[['Incolla da Excel','pasteDlg()'],['Copia tabella','copyT()'],['Trova e sostituisci','frDlg()'],['Imposta colonna','setDlg()'],['Rimuovi duplicati','dupDlg()'],['Duplica tabella','cloneT()'],['Esporta CSV','csvT()'],['Esporta Excel','xlsT()']].map(([l,f])=>`<button onclick="this.closest('details').open=false;${f}">${l}</button>`).join('')}</div></details><span style="flex:1"></span><button class="pri" onclick="addRow()">+ Riga</button></div>
<div class="sc tbl"><table><tr><th class="n"><input type="checkbox" ${all?'checked':''} aria-label="Seleziona tutte" onchange="selAll(this.checked)"></th>${vf.map(f=>`<th class="srt" title="Ordina" onclick="sortT('${f.n}')">${E(f.n)}${f.q?' *':''}${so&&so.c==f.n?(so.d==1?' ▲':' ▼'):''}</th>`).join('')}<th></th></tr>
<tr class="fr"><th></th>${vf.map(f=>`<th><input data-c="${E(f.n)}" placeholder="⌕" value="${E(S.cf[f.n]||'')}" title="Filtra: testo, >5, <5, =x, !x" oninput="cfSet('${f.n}',this.value)"></th>`).join('')}<th>${cfs.length?'<button class="ib" title="Azzera filtri" aria-label="Azzera filtri" onclick="S.cf={};S.pg=0;draw()">✕</button>':''}</th></tr>
${pr.map(([r,i])=>`<tr data-i="${i}" class="${sl(i)?'sl':''}"><td class="n"><input type="checkbox" ${sl(i)?'checked':''} aria-label="Seleziona riga" onchange="selR(${i},this.checked)"></td>${vf.map(f=>`<td class="${f.q&&r[f.n]===''?'rq':''}">${cell(S.t,f,r[f.n],`upd(${i},'${f.n}',this)`)}</td>`).join('')}<td class="act"><button class="ib" title="Duplica riga" aria-label="Duplica riga" onclick="dupRow(${i})">⧉</button><button class="ib x" title="Elimina riga" aria-label="Elimina riga" onclick="del(${i})">✕</button></td></tr>`).join('')||`<tr><td colspan="${vf.length+2}" class="mu">Nessuna riga</td></tr>`}
${tot.some(x=>x!==null)?`<tr class="tt"><td></td>${tot.map((x,k)=>`<td>${x===null?'':'Σ '+(vf[k].cur?eur(x):x.toLocaleString('it-IT'))}</td>`).join('')}<td></td></tr>`:''}
<tr class="adr" onclick="addRow()"><td colspan="${vf.length+2}">+</td></tr></table></div>
${rows.length>50?`<div class="pg"><button class="ib" aria-label="Pagina precedente" onclick="pgGo(-1)" ${S.pg?'':'disabled'}>‹</button><span>${S.pg+1}/${np}</span><button class="ib" aria-label="Pagina successiva" onclick="pgGo(1)" ${S.pg<np-1?'':'disabled'}>›</button><select aria-label="Righe per pagina" onchange="psSet(this.value)">${[50,100,250,500].map(x=>`<option ${x==S.ps?'selected':''}>${x}</option>`).join('')}</select></div>`:''}
<details class="fd" ${S.dt?'open':''} ontoggle="S.dt=this.open"><summary>Campi</summary>
<div class="row"><input value="${E(S.t)}" title="Rinomina tabella" aria-label="Nome tabella" onchange="renT(this.value)"></div>
${t.f.map(f=>`<div class="row"><input value="${E(f.n)}" ${f.n=='id'?'disabled':''} onchange="renF('${f.n}',this.value)"><select onchange="typF('${f.n}',this.value)">${TL.map(x=>`<option ${x==(f.cur?'valuta':f.t)?'selected':''}>${x}</option>`).join('')}</select>${f.t=='scelta'?`<input class="opt" placeholder="A, B, C" value="${E((f.o||[]).join(', '))}" onchange="setOpt('${f.n}',this.value)">`:''}${f.t=='calcolo'?`<input class="opt" placeholder="{prezzo}*{quantita}" value="${E(f.fx||'')}" onchange="setFx('${f.n}',this.value)">`:''}<label title="Obbligatorio"><input type="checkbox" ${f.q?'checked':''} ${f.n=='id'?'disabled':''} onchange="reqF('${f.n}',this.checked)"> *</label><button class="ib ${f.h?'':'on'}" title="Mostra / nascondi colonna" aria-label="Mostra o nascondi colonna" onclick="hideF('${f.n}')">${EYE}</button><button class="ib" title="Sposta su" aria-label="Sposta su" onclick="moveF('${f.n}',-1)">↑</button><button class="ib" title="Sposta giù" aria-label="Sposta giù" onclick="moveF('${f.n}',1)">↓</button>${f.n=='id'?'':`<button class="x" title="Elimina campo" aria-label="Elimina campo" onclick="delF('${f.n}')">✕</button>`}</div>`).join('')}
<div class="row"><input id="nf" placeholder="Nuovo campo"><select id="nt">${TL.map(x=>`<option>${x}</option>`).join('')}</select><label title="Obbligatorio"><input type="checkbox" id="nq"> *</label><button onclick="addF()">+</button></div></details>`};
recalcAll();
/* Guida e primi passi */

V.guida=()=>`<h2>Come funziona</h2><p class="hint">Mini-Access tiene i tuoi dati in tabelle, come un foglio con regole. Tutto si salva da solo su questo dispositivo.</p>
<div class="card"><h3 style="margin-top:0">Il percorso in 4 passi</h3><ol class="steps"><li><b>Scrivi i dati</b><span class="mu">In Tabelle ogni colonna è un campo e ogni riga un record.</span><button onclick="go('tabelle')">Apri Tabelle</button></li><li><b>Collega le tabelle</b><span class="mu">Facoltativo: in Relazioni scegli i valori da un menu invece di riscriverli.</span><button onclick="go('relazioni')">Apri Relazioni</button></li><li><b>Cerca e modifica</b><span class="mu">Query filtra e raggruppa, Maschere modifica un record alla volta.</span><button onclick="go('query')">Apri Query</button></li><li><b>Crea il risultato</b><span class="mu">Report per stampare, Macro per ripetere azioni, Importa / Esporta per i file.</span><button onclick="go('report')">Apri Report</button></li></ol></div>
<div class="gd"><div class="card"><h3 style="margin-top:0">Scrivere nelle tabelle</h3><dl style="margin:0"><dt>Aggiungere e duplicare</dt><dd>«+ Nuova riga» crea una riga e ti porta nella prima cella. ⧉ duplica una riga.</dd><dt>Ordinare e filtrare</dt><dd>Clicca un’intestazione per ordinare (di nuovo per invertire, ancora per togliere). Il campo sopra la tabella filtra.</dd><dt>Cambiare la struttura</dt><dd>Apri «Struttura»: rinomina tabella e campi, cambia tipo, rendi obbligatorio o elimina.</dd><dt>Sbagliato?</dt><dd>Ctrl+Z oppure il pulsante ↶ in alto annulla l’ultima modifica.</dd></dl></div>
<div class="card"><h3 style="margin-top:0">Scorciatoie</h3><dl style="margin:0"><dt><kbd>Ctrl</kbd>+<kbd>K</kbd></dt><dd>Scrivi un comando in Inizio, ad esempio «apri ordini».</dd><dt><kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd></dt><dd>Passa alla tabella precedente o successiva.</dd><dt>Barra in alto</dt><dd>Scegli la tabella attiva, cerca in tutti i dati, aggiungi un record. «Altro» contiene esporta, segnalibro, tema e lingua.</dd></dl></div></div>
<div class="row"><button onclick="UI.all('guide',1);go('home')">Mostra i primi passi in Inizio</button></div>`;
const _vh=V.home;V.home=()=>(U.guide?`<div class="card"><div class="row" style="margin:0"><h3 style="margin:0;border:0;padding:0">Primi passi</h3><span style="flex:1"></span><button onclick="go('guida')">Come funziona</button><button onclick="UI.all('guide',0)">Nascondi</button></div><ol class="steps"><li><b>Scrivi i dati</b><button onclick="go('tabelle')">Tabelle</button></li><li><b>Collega</b><button onclick="go('relazioni')">Relazioni</button></li><li><b>Cerca e modifica</b><button onclick="go('query')">Query</button></li><li><b>Crea il risultato</b><button onclick="go('report')">Report</button></li></ol></div>`:'')+_vh();
const HT={};
/* Barra semplificata */
document.querySelector('.tbar').remove();
const mc=()=>{const d=document.querySelector('.more');d&&(d.open=false)};
$('main').insertAdjacentHTML('afterbegin',`<div class="tbar"><button class="ib" title="Annulla ultima modifica (Ctrl+Z)" aria-label="Annulla" onclick="undo()"><svg viewBox="0 0 24 24"><path d="M9 14L4 9l5-5M4 9h9a6 6 0 0 1 0 12h-3"/></svg></button><select id="ts" class="ts" aria-label="Tabella attiva" onchange="tsw(this.value)"></select><input id="sq" class="sch" placeholder="Ricerca" autocomplete="off" oninput="tbQ(this.value)"><button class="pri" onclick="tbNew()">+ Record</button>
<details class="more"><summary>Altro</summary><div class="mm"><button onclick="mc();S.io=JSON.stringify(db,null,1);go('dati')">Esporta database</button><button onclick="mc();tbBm()">Aggiungi sezione a Inizio</button><button onclick="mc();tbTh()">Chiaro / scuro</button><label>Lingua<select id="lg" onchange="UI.set('lang',this.value);draw()">${Object.entries(LN).map(([k,v])=>`<option value="${k}" ${k==U.lang?'selected':''}>${v}</option>`).join('')}</select></label></div></details></div>`);
TR.push(['Come funziona','How it works','Cómo funciona','Comment ça marche','So funktioniert’s'],['Altro','More','Más','Plus','Mehr'],['+ Record','+ Record','+ Registro','+ Enregistrement','+ Datensatz'],['Primi passi','Getting started','Primeros pasos','Premiers pas','Erste Schritte'],['Nascondi','Hide','Ocultar','Masquer','Ausblenden'],['Scrivi i dati','Enter data','Escribe los datos','Saisir les données','Daten eingeben'],['Collega','Link','Conecta','Relier','Verknüpfen'],['Cerca e modifica','Find and edit','Busca y edita','Chercher et modifier','Suchen und bearbeiten'],['Crea il risultato','Create the output','Crea el resultado','Créer le résultat','Ergebnis erstellen']);
const _d2=draw;draw=function(){_d2();const h=HT[S.tab],e=$('#v h2');if(h&&e&&!(e.nextElementSibling&&e.nextElementSibling.classList.contains('hint')))e.insertAdjacentHTML('afterend',`<p class="hint">${h}</p>`)};
ap();draw();
</script>
<script>
/* ===== v6: funzioni più intuitive ===== */
document.head.insertAdjacentHTML('beforeend','<style>.qs{max-width:none;margin:.2rem 0 .8rem}.qs b{color:var(--tx)}.hint b{color:var(--tx)}</style>');
Object.assign(HT,{
tabelle:'Qui scrivi i dati: ogni colonna è un <b>campo</b>, ogni riga un <b>record</b>. Clicca una cella per modificarla: si salva da sola.',
relazioni:'Collega due tabelle: un campo sceglierà i valori da un menu preso dall’altra tabella (es. l’ordine sceglie il cliente).',
maschere:'Una maschera mostra <b>un record alla volta</b> in un modulo: scorri con le frecce, poi premi Salva.',
report:'Il report è una pagina pronta da stampare: scegli la tabella, come raggruppare e cosa sommare.',
macro:'Una macro è una <b>sequenza di azioni</b> da rieseguire con un clic: aggiungi i passi in ordine, poi salva.',
dati:'<b>Esporta</b> per portare i dati fuori (Excel, CSV, copia di sicurezza). <b>Importa</b> per portarne dentro.',
note:'Un blocco note libero: si salva da solo e si può tradurre.'});
/* menu: Note e Guida raggiungibili */
GR.note='Output';GR.guida='Impostazioni';TABS.splice(TABS.length-1,0,['note','Note']);TABS.push(['guida','Come funziona']);
/* reset chiaro */
rst=function(){if(!confirm('Cancellare tutte le tabelle e tutti i dati?'))return;db=seed();S.t=undefined;S.rec=0;S.q=qd();S.rp={title:'Riepilogo'};S.macro=[];sv();draw()};
TR.push(['Cancella tutti i dati','Delete all data','Borrar todos los datos','Effacer toutes les données','Alle Daten löschen']);
/* download */
function dlf(n,t,m){try{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:m}));a.download=n;a.click();M('File scaricato: '+n,1)}catch{M('Download non disponibile')}}
const dbDl=()=>dlf('database.json',JSON.stringify(db,null,1),'application/json');
function jsonFile(el){const f=el.files[0];if(!f)return;const r=new FileReader();r.onload=()=>{if(confirm('Sostituire tutti i dati attuali con quelli del file?')){S.io=r.result;impJ()}};r.readAsText(f)}
expQ=function(){const{cols,rows}=run(),q=v=>'"'+String(v??'').replace(/"/g,'""')+'"';dlf('query.csv','\ufeff'+[cols,...rows.map(r=>cols.map(c=>dq(c,r[c])))].map(r=>r.map(q).join(';')).join('\n'),'text/csv')};
/* Importa / Esporta a schede */
V.dati=()=>{const t=T();return `<h2>Importa / Esporta</h2>${tbSel()}<div class="gd">
<div class="card"><h3 style="margin-top:0">Esporta</h3><p class="mu">Scarica «${E(S.t||'')}» per usarla in Excel.</p><div class="row">${t?'<button onclick="csvT()">Scarica CSV</button><button onclick="xlsT()">Scarica Excel</button><button onclick="copyT()">Copia per Excel</button>':'<span class="mu">Nessuna tabella</span>'}</div><p class="mu">Oppure salva una copia di sicurezza di tutto.</p><div class="row"><button onclick="dbDl()">Scarica database (JSON)</button></div></div>
<div class="card"><h3 style="margin-top:0">Importa</h3><p class="mu">Incolla le celle copiate da Excel o scegli un file CSV: le aggiungi a una tabella o ne crei una nuova.</p><div class="row"><button class="pri" onclick="pasteDlg()">Incolla o apri file CSV</button></div><p class="mu">Per rimettere una copia di sicurezza scegli il file JSON.</p><div class="row"><input type="file" accept=".json" onchange="jsonFile(this)"></div></div></div>
${S.io?`<h3>Testo esportato</h3><textarea rows="10" spellcheck="false" oninput="S.io=this.value">${E(S.io)}</textarea><div class="row"><input id="ni" placeholder="nome nuova tabella"><button onclick="impCSV()">Importa questo testo come tabella</button><button onclick="impJ()">Ripristina database da questo JSON</button><button onclick="S.io='';draw()">Chiudi</button></div>`:''}`};
const _pd=pasteDlg;pasteDlg=function(){_pd();if(!T()){const m=$('#pm');m.value='n';m.disabled=true}};
/* Relazioni a frase */
S.rl={};
function rlS(){const k=Object.keys(db.tables),r=S.rl;if(!k.includes(r.ta))r.ta='';if(!k.includes(r.tb)||r.tb==r.ta)r.tb='';const fa=r.ta?T(r.ta).f.map(f=>f.n):[],fb=r.tb?T(r.tb).f.map(f=>f.n):[];if(!fa.includes(r.fa))r.fa='';if(!fb.includes(r.fb))r.fb='';return{k,fa,fb}}
function RL(k,v){S.rl[k]=v;draw()}
function addR2(){const r=S.rl;if(!r.ta||!r.fa||!r.tb||!r.fb)return M('Scegli tutte e quattro le voci');const a=r.ta+'.'+r.fa,b=r.tb+'.'+r.fb;if(db.rel.some(x=>x.a==a&&x.b==b))return M('Relazione già presente');if(T(r.ta).r.some(x=>x[r.fa]!==''&&!T(r.tb).r.some(y=>y[r.fb]==x[r.fa])))return M('Impossibile: ci sono valori in '+a+' senza corrispondenza in '+b);db.rel.push({a,b});sv();draw()}
V.relazioni=()=>{const{k,fa,fb}=rlS(),r=S.rl,sel=(id,a,v)=>`<select onchange="RL('${id}',this.value)"><option value="">— scegli —</option>${a.map(x=>`<option ${x==v?'selected':''}>${E(x)}</option>`).join('')}</select>`;
return `<h2>Relazioni</h2><ul class="rl">${db.rel.map((x,i)=>{const[a1,a2]=x.a.split('.'),[b1,b2]=x.b.split('.');return `<li>In <b>${E(a1)}</b> il campo <b>${E(a2)}</b> sceglie un record di <b>${E(b1)}</b> (${E(b2)})<span class="mu">uno-a-molti</span><button class="x" onclick="db.rel.splice(${i},1);sv();draw()">✕</button></li>`}).join('')||'<li class="mu">Nessuna relazione</li>'}</ul>
${k.length<2?'<p class="mu">Servono almeno due tabelle per creare una relazione.</p>':`<div class="card"><h3 style="margin-top:0">Nuova relazione</h3><div class="row">In ${sel('ta',k,r.ta)} il campo ${sel('fa',fa,r.fa)} sceglie un record di ${sel('tb',k.filter(x=>x!=r.ta),r.tb)} tramite il campo ${sel('fb',fb,r.fb)}<button class="pri" onclick="addR2()">Crea relazione</button></div></div>`}`};
/* Query: numerata, con frase riassuntiva */
const _vq=V.query;V.query=()=>{const q=S.q,r=run(),x=q.j!==''&&db.rel[q.j],o=x?(q.t==x.a.split('.')[0]?x.b:x.a).split('.')[0]:'';
const s=`Stai guardando <b>${E(q.t)}</b>${x?' unita a <b>'+E(o)+'</b>':''}${q.ff&&q.fv!==''?`, solo dove <b>${E(q.ff)}</b> ${E(q.op)} <b>${E(q.fv)}</b>`:''}${q.of?`, ordinata per <b>${E(q.of)}</b> (${q.od})`:''}${q.ag&&q.gb?`, raggruppata per <b>${E(q.gb)}</b> con ${q.ag}${q.af?' di <b>'+E(q.af)+'</b>':''}`:''}: <b>${r.rows.length}</b> risultati.`;
return _vq().replace('</h2>',`</h2><p class="hint">Una query risponde a una domanda sui tuoi dati: imposta i punti qui sotto, i risultati si aggiornano subito.</p><p class="mu qs">${s}</p>`)
.replace('<label>Tabella ','<label>1. Dati da ').replace('<label>Unisci con ','<label>2. Unisci con (tabella collegata) ').replace('<label>Filtra ','<label>3. Mostra solo le righe dove ').replace('<label>Ordina ','<label>4. Ordina per ').replace('<label>Raggruppa per ','<label>5. Raggruppa per ').replace(' calcola ',' e calcola ')
.replace('<div class="chk">','<h3>Colonne da mostrare</h3><div class="chk">').replace('<b>Modifica in blocco</b> sui risultati','<b>Azioni sui risultati</b>: imposta un campo su tutte le righe trovate, oppure eliminale')};
/* Macro: campi che si adattano al passo scelto */
S.ma='tab';
const _vm=V.macro;V.macro=()=>{const m=S.ma=='msg',n=S.macro.length;return _vm().replace('<select id="ma">','<select id="ma" onchange="S.ma=this.value;draw()">').replace(`<option value="${S.ma}">`,`<option value="${S.ma}" selected>`)
.replace('<select id="mt">',`<select id="mt" ${m?'hidden':''}>`).replace('<input id="mx" placeholder="testo (solo per messaggio)"',`<input id="mx" ${m?'':'hidden'} placeholder="Testo del messaggio"`)
.replace('<div class="row"><select id="ma"',`<p class="mu">${n?'Passi aggiunti: '+n+'. Aggiungine altri oppure salva.':'Scegli un’azione, poi premi «+ Aggiungi passo». Quando hai finito, dai un nome e premi «Salva macro».'}</p><div class="row"><select id="ma"`)
.replace('<button class="pri" onclick="saveM()">',`${n?'<button onclick="S.macro.pop();draw()">↶ Togli ultimo passo</button>':''}<button class="pri" onclick="saveM()">`)};
/* Inizio: primo avvio guidato */
const _vh2=V.home;V.home=()=>(Object.keys(db.tables).length?'':`<div class="card"><h3 style="margin-top:0">Da dove cominci?</h3><p class="mu">Non hai ancora nessuna tabella: scegli come iniziare.</p><div class="row"><button class="pri" onclick="newT()">Crea la prima tabella</button><button onclick="pasteDlg()">Incolla da Excel o apri CSV</button><button onclick="go('guida')">Come funziona</button></div></div>`)+_vh2();
/* piccoli ritocchi a Tabelle e menu */
const _d3=draw;draw=function(){_d3();const q=s=>document.querySelector(s),nb=q('button[aria-label="Nuova tabella"]');if(nb)nb.textContent='+ Tabella';const nd=q('.tdel');if(nd)nd.textContent='✕ Elimina tabella';
const rb=q('aside button[onclick="rst()"]');if(rb)rb.textContent=TR.find(x=>x[0]=='Cancella tutti i dati')[Math.max(0,LG.indexOf(U.lang))];
if(S.tab=='tabelle'&&T()){const tm=q('details.tm');if(tm&&!q('#bf2'))tm.insertAdjacentHTML('beforebegin','<button id="bf2" onclick="S.dt=1;draw();q2()">Campi</button>');
const sc=q('.tbl');if(sc&&!q('#th2'))sc.insertAdjacentHTML('afterend','<p class="mu" id="th2" style="font-size:.85rem;margin:.3rem 0">Clicca un’intestazione per ordinare · scrivi sotto l’intestazione per filtrare (es. <kbd>&gt;100</kbd>, <kbd>=Rossi</kbd>, <kbd>!x</kbd>) · <kbd>Ctrl</kbd>+<kbd>Invio</kbd> aggiunge una riga</p>');
const fs=q('.fd summary');if(fs)fs.textContent='Campi: aggiungi, rinomina o cambia tipo alle colonne'}};
const q2=()=>setTimeout(()=>{const e=document.querySelector('.fd');e&&e.scrollIntoView({behavior:'smooth',block:'start'})},50);
draw();
</script>
<script>
/* ===== v7: tabelle nuove completamente vuote ===== */
function mkT(n){db.tables[n]={f:[],r:[]};S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};S.dt=1;S.tab='tabelle';sv();draw()}
newT=function(){const n=nm(prompt('Nome della nuova tabella')||'');if(!n)return;if(db.tables[n])return M('Nome già usato');mkT(n)};
addT=function(){const n=nm($('#nn').value);if(!n||db.tables[n])return M('Nome tabella mancante o già usato');mkT(n)};
const _ar2=addRow;addRow=function(){if(!T().f.length)return M('Aggiungi prima almeno un campo (colonna)');_ar2()};
const _nr=newRec;newRec=function(){if(!T().f.length)return M('Aggiungi prima almeno un campo (colonna)');_nr()};
const _tn=tbNew;tbNew=function(){if(T()&&!T().f.length){S.dt=1;go('tabelle');return M('Aggiungi prima almeno un campo (colonna)')}_tn()};
const _d4=draw;draw=function(){_d4();if(S.tab=='tabelle'&&T()&&!T().f.length){const h=document.querySelector('#v h2');if(h&&!document.getElementById('emp'))h.insertAdjacentHTML('afterend',`<div class="card" id="emp"><b>La tabella «${E(S.t)}» è vuota.</b><p class="mu" style="margin:.3rem 0 0">Scrivi il nome del primo campo (una colonna, es. «nome»), scegli il tipo e premi «+» in fondo, nella sezione Campi.</p></div>`);const f=document.querySelector('.fd');f&&(f.open=true)}};
draw();
</script>
<script>
/* ===== v8: niente preselezioni, scegli tutto tu ===== */
S.ma='';
const _vm3=V.macro;V.macro=()=>_vm3().replace(/(<select id="ma"[^>]*>)/,`$1<option value="" ${S.ma?'':'selected'}>— scegli azione —</option>`).replace(/(<select id="mt"[^>]*>)/,'$1<option value="">— scegli tabella —</option>');
const _as=addStep;addStep=function(){if(!$('#ma').value)return M('Scegli prima l’azione');if($('#ma').value!='msg'&&!$('#mt').value)return M('Scegli la tabella');_as()};
S.rp={title:'Riepilogo',t:S.t,g:'',s:''};S.rl={};
draw();
</script>
<style>
.tbl .fr{display:none}.tbl.fo .fr{display:table-row}
.tdel{display:none!important}
.fd{border:1px solid var(--ln);border-radius:14px;padding:.4rem .9rem .8rem;background:rgba(var(--ink),.03)}
.fd h4{margin:1rem 0 .1rem;font-size:.75rem;font-weight:600;color:var(--mu);text-transform:uppercase;letter-spacing:.05em}
</style>
<script>
/* ===== v9: tabelle più pulite ===== */
mkT=function(n){db.tables[n]={f:[],r:[]};S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};S.dt=0;S.tab='tabelle';sv();draw()};
const _af3=addF;addF=function(){S.dt=1;_af3()};
const _d5=draw;draw=function(){_d5();if(S.tab!='tabelle'||!T())return;const q=s=>document.querySelector(s);
const h=q('#th2');h&&h.remove();
const si=q('.sch2');if(si){si.placeholder='Cerca nella tabella';si.title='Cerca in tutte le colonne'}
const tb=q('.tbl');if(tb&&(S.fo||Object.values(S.cf).some(v=>v)))tb.classList.add('fo');
const mm=q('details.tm .mm');if(mm)mm.insertAdjacentHTML('afterbegin','<button title="Scrivi sotto l’intestazione: &gt;100, =Rossi, !x" onclick="this.closest(\'details\').open=false;S.fo=!S.fo;draw()">'+(S.fo?'Nascondi':'Mostra')+' filtri per colonna</button>');
const fd=q('.fd');if(!fd||fd.dataset.k)return;fd.dataset.k=1;
const rows=[...fd.children].filter(e=>e.classList.contains('row'));
if(rows.length>1){rows[0].insertAdjacentHTML('afterbegin','<span class="mu">Nome tabella</span>');rows[0].insertAdjacentHTML('beforebegin','<h4>Tabella</h4>');rows[1].insertAdjacentHTML('beforebegin','<h4>Colonne</h4>');const last=rows[rows.length-1];last.insertAdjacentHTML('beforebegin','<h4>Nuova colonna</h4>')}
fd.querySelectorAll('label[title="Obbligatorio"]').forEach(l=>{l.lastChild.nodeValue=' obbligatorio'});
const d=document.createElement('div');d.className='row';d.style.marginTop='1rem';d.innerHTML='<button class="x"></button>';const b=d.firstChild;b.textContent='Elimina tabella «'+S.t+'»';b.onclick=()=>confirm('Eliminare «'+S.t+'» e tutti i suoi dati?')&&delT();fd.appendChild(d)};
draw();
</script>
<script>
/* ===== v10: creazione tabella su misura ===== */
const NTY=['testo','numero','valuta','data','sì/no','scelta','link','calcolo','collegamento'];
const ntNew=n=>({n:n||'',idc:0,c:[{n:'',t:'testo',q:0,x:''}]});
function ntOpen(n){S.nt=ntNew(n);ntDraw()}
function ntDraw(){const s=S.nt,tbs=Object.keys(db.tables).filter(k=>T(k).f.length),ty=NTY.filter(x=>x!='collegamento'||tbs.length);
const row=(c,i)=>`<div class="row"><input placeholder="Nome colonna" value="${E(c.n)}" oninput="S.nt.c[${i}].n=this.value"><select onchange="ntT(${i},this.value)">${ty.map(x=>`<option ${x==c.t?'selected':''}>${x}</option>`).join('')}</select>
${c.t=='scelta'?`<input class="opt" placeholder="Opzioni: A, B, C" value="${E(c.x)}" oninput="S.nt.c[${i}].x=this.value">`:c.t=='calcolo'?`<input class="opt" placeholder="{prezzo}*{quantita}" value="${E(c.x)}" oninput="S.nt.c[${i}].x=this.value">`:c.t=='collegamento'?`<select onchange="S.nt.c[${i}].x=this.value"><option value="">scegli tabella</option>${tbs.map(k=>`<option ${k==c.x?'selected':''}>${E(k)}</option>`).join('')}</select>`:''}
${c.t=='calcolo'?'':`<label><input type="checkbox" ${c.q?'checked':''} onchange="S.nt.c[${i}].q=this.checked"> obbligatorio</label>`}
<button class="ib" aria-label="Su" onclick="ntMv(${i},-1)">↑</button><button class="ib" aria-label="Giù" onclick="ntMv(${i},1)">↓</button><button class="ib x" aria-label="Togli colonna" onclick="ntDel(${i})">✕</button></div>`;
dlg(`<h3>Nuova tabella</h3><label class="fl"><span>Nome tabella</span><input value="${E(s.n)}" placeholder="es. Clienti" oninput="S.nt.n=this.value"></label>
<label class="fl"><span>Numero automatico (id)</span><input type="checkbox" ${s.idc?'checked':''} onchange="S.nt.idc=this.checked"></label>
<h3>Colonne</h3>${s.c.map(row).join('')}<div class="row"><button onclick="S.nt.c.push({n:'',t:'testo',q:0,x:''});ntDraw()">+ Colonna</button><span style="flex:1"></span><button class="pri" onclick="ntGo()">Crea tabella</button></div>`)}
function ntT(i,t){S.nt.c[i].t=t;S.nt.c[i].x='';ntDraw()}
function ntMv(i,d){const c=S.nt.c,j=i+d;if(j<0||j>=c.length)return;[c[i],c[j]]=[c[j],c[i]];ntDraw()}
function ntDel(i){S.nt.c.splice(i,1);if(!S.nt.c.length)S.nt.c.push({n:'',t:'testo',q:0,x:''});ntDraw()}
function ntGo(){const s=S.nt,n=nm(s.n);if(!n)return M('Scrivi il nome della tabella');if(db.tables[n])return M('Esiste già una tabella con questo nome');
const f=[],rel=[],seen=new Set(s.idc?['id']:[]);if(s.idc)f.push({n:'id',t:'numero',q:1});
for(const c of s.c){const k=nm(c.n);if(!k)return M('Ogni colonna ha bisogno di un nome (o toglila con ✕)');if(seen.has(k))return M('Nome colonna ripetuto: '+k);seen.add(k);const o={n:k,t:c.t};
if(c.t=='valuta'){o.t='numero';o.cur=1}
else if(c.t=='scelta')o.o=c.x.split(',').map(x=>x.trim()).filter(Boolean);
else if(c.t=='calcolo')o.fx=c.x;
else if(c.t=='collegamento'){const d=T(c.x);if(!d)return M('«'+k+'»: scegli la tabella da collegare');const kf=d.f.find(g=>g.n=='id')||d.f[0];o.t=kf.t=='testo'?'testo':'numero';rel.push({a:n+'.'+k,b:c.x+'.'+kf.n})}
if(c.q&&c.t!='calcolo')o.q=1;f.push(o)}
db.tables[n]={f,r:[]};rel.forEach(r=>db.rel.push(r));S.nt=null;S.t=n;S.q=qd(n);S.rp={...S.rp,...rpDef(n)};S.tab='tabelle';S.dt=0;sv();dgc();M('Tabella «'+n+'» creata',1);draw()}
newT=()=>ntOpen();
addT=function(){const e=$('#nn');ntOpen(e?e.value:'')};
draw();
</script>
<style>
@property --a{syntax:'<angle>';inherits:false;initial-value:0deg}
.cred{position:relative;margin-top:.6rem;padding:.75rem .9rem;border-radius:16px;font-size:.82rem;line-height:1.5;text-align:center}
.cred::before{content:"";position:absolute;inset:0;border-radius:inherit;padding:2.5px;background:conic-gradient(from var(--a),#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:rgbspin 3s linear infinite;pointer-events:none}
.cred::after{content:"";position:absolute;inset:-3px;border-radius:19px;background:conic-gradient(from var(--a),#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00);filter:blur(9px);opacity:.35;z-index:-1;animation:rgbspin 3s linear infinite;pointer-events:none}
.cred b{display:block;font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;opacity:.7}
.cred a{display:block;color:inherit;font-weight:600;text-decoration:underline;text-underline-offset:2px}
@keyframes rgbspin{to{--a:360deg}}
@media(prefers-reduced-motion:reduce){.cred::before,.cred::after{animation:none}}
</style>
<script>
document.querySelector('aside').insertAdjacentHTML('beforeend','<div class="cred"><b>Creato da</b><a href="https://github.com/mikaelzer0" target="_blank" rel="noopener">@mikaelzer0</a><a href="https://it.fiverr.com/mikaelzero" target="_blank" rel="noopener">Fiverr · mikaelzero</a><a href="https://github.com/mikaelzer0" target="_blank" rel="noopener">GitHub · mikaelzer0</a></div>');
</script>
</body>
</html>
'''

if __name__ == "__main__":
    main()
