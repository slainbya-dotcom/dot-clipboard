"""Inlines CSS/JS into single-file HTML previews (with a fake Tauri bridge and
sample settings) so the UI can be checked in any browser without building.

  python3 tools/build_preview.py [out_dir] [path/to/dot-clock]

If the Dot Clock project is given, also writes clipboard-side-by-side.html showing both styles under Dot Clock
widgets together, with Dot Clipboard matching Dot Clock's look."""
import html, json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "preview")
WT_ROOT = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT, exist_ok=True)

WORLD_TIME_SAMPLE = {
    "clocks": [
        {"id": "h", "label": "London, UK", "tz": "Europe/London", "lat": 51.51, "lng": -0.13, "home": True},
        {"id": "a", "label": "New York, USA", "tz": "America/New_York", "lat": 40.71, "lng": -74.01},
        {"id": "b", "label": "Tokyo, Japan", "tz": "Asia/Tokyo", "lat": 35.68, "lng": 139.69},
    ],
    "use24h": True, "dotColor": "#ffb000", "dotSize": 3, "bgColor": "#101010", "bgOpacity": 0.85,
}

TIMER_SAMPLE_JS = """({ matchWorldTime: %(match)s, style: '%(style)s', clips: [
    { id: 'a', text: 'https://github.com/slainbya-dotcom/dot-clock', at: Date.now() - 120000, pinned: false },
    { id: 'b', text: 'Meeting moved to 3pm Thursday, same room', at: Date.now() - 540000, pinned: false },
    { id: 'c', text: '07700 900123', at: Date.now() - 2400000, pinned: true },
    { id: 'd', text: 'stephen@example.com', at: Date.now() - 3900000, pinned: true },
    { id: 'e', text: 'Order #A-55102 shipped via Royal Mail', at: Date.now() - 10800000, pinned: false },
    { id: 'f', text: '£1,249.99', at: Date.now() - 18000000, pinned: false } ] })"""


def shim(match=True, style="history"):
    state_js = TIMER_SAMPLE_JS % {"match": "true" if match else "false", "style": style}
    return """<script>
window.__PREVIEW__ = true;
var __state = JSON.stringify(%s);
window.__TAURI__ = {
  core: { invoke: async (cmd, args) => {
    if (cmd === 'load_state') return __state;
    if (cmd === 'read_world_time') return %s;
    if (cmd === 'save_state') { __state = args.json; return; }
  } },
  event: { listen: async () => () => {} },
  window: { getCurrentWindow: () => ({ setSize: async () => {}, setAlwaysOnTop: async () => {}, startDragging: async () => {} }) },
  dpi: { LogicalSize: function (w, h) { this.width = w; this.height = h; } },
};
</script>""" % (state_js, json.dumps(json.dumps(WORLD_TIME_SAMPLE)))


def inline(root, name, head=""):
    src = open(os.path.join(root, "src", name), encoding="utf-8").read()
    src = re.sub(r'<link rel="stylesheet" href="([^"]+)">',
                 lambda m: "<style>" + open(os.path.join(root, "src", m.group(1)), encoding="utf-8").read() + "</style>", src)
    src = re.sub(r'<script src="([^"]+)"></script>',
                 lambda m: "<script>" + open(os.path.join(root, "src", m.group(1)), encoding="utf-8").read()
                 .replace("</script", "<\\/script") + "</script>", src)
    return src.replace("</head>", head + "</head>", 1)


DESK = "<style>body{min-height:100vh;padding:24px;background:linear-gradient(135deg,#3a6186,#89253e)!important}</style>"
open(os.path.join(OUT, "clipboard-widget-preview.html"), "w", encoding="utf-8").write(inline(ROOT, "index.html", DESK + shim()))
open(os.path.join(OUT, "clipboard-settings-preview.html"), "w", encoding="utf-8").write(inline(ROOT, "settings.html", shim()))

if WT_ROOT:
    wt_shim = """<script>window.__TAURI__ = { core: { invoke: async (c) => c === 'load_state' ? %s : undefined },
      event: { listen: async () => () => {} },
      window: { getCurrentWindow: () => ({ setSize: async () => {}, setAlwaysOnTop: async () => {}, startDragging: async () => {} }) },
      dpi: { LogicalSize: function () {} } };</script>""" % json.dumps(json.dumps(WORLD_TIME_SAMPLE))
    wt_doc = inline(WT_ROOT, "index.html", wt_shim)
    frames = "".join('<div class="cap">%s</div><iframe style="height:%dpx" srcdoc="%s"></iframe>\n'
                     % (t, h, html.escape(inline(ROOT, "index.html", shim(True, sid)), quote=True))
                     for sid, t, h in [("history", "A · History", 190), ("latest", "B · Latest", 70)])
    page = """<!doctype html><html><head><meta charset="utf-8"><title>Side by side</title>
<style>body{margin:0;min-height:100vh;padding:24px;box-sizing:border-box;background:linear-gradient(135deg,#3a6186,#89253e);
font:12px system-ui;color:#fff}iframe{border:0;display:block;background:transparent;width:100%%;}
.cap{opacity:.75;margin:12px 0 4px}#try{margin-top:18px;max-width:520px;background:rgba(0,0,0,.25);border-radius:10px;padding:10px 14px;line-height:1.6}
code{background:rgba(255,255,255,.12);padding:1px 5px;border-radius:4px}</style></head><body>
<div class="cap">Dot Clock</div><iframe id="a" style="height:100px" srcdoc="%s"></iframe>
%s
<div id="try"><b>Try it:</b> select one of these and press Ctrl+C (Cmd+C):<br><code>Hello from Dot Clipboard</code> · <code>https://open-meteo.com</code> · <code>$42.50</code> · <code>Send the invoice before Friday</code></div>
<script>document.addEventListener('copy', () => { const s = String(getSelection() || ''); if (s.trim()) for (const f of document.querySelectorAll('iframe')) f.contentWindow.postMessage({ clip: s }, '*'); });</script>
</body></html>""" % (html.escape(wt_doc, quote=True), frames)
    open(os.path.join(OUT, "clipboard-side-by-side.html"), "w", encoding="utf-8").write(page)

print("previews written to", os.path.abspath(OUT))
