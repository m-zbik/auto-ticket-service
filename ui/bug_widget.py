"""Self-contained 🐞 bug-reporter widget (the reusable drop-in).

Renders a mock app screen with a floating ladybug button. Tapping it does exactly
what the iOS app does:

    1. captures a screenshot of the current screen (html2canvas over its own DOM),
    2. lets you draw on it with a red marker (freehand canvas, like PencilKit),
    3. collects a title / description / category,
    4. sends the annotated screenshot straight to the auto-ticket service.

No file upload. Everything lives in one iframe document so the screenshot is of
real rendered content, and the POST goes browser → service directly (CORS is open
on the API). This is intentionally framework-free HTML/JS: it's the same thing you
would paste into any real host app (see docs/INTEGRATION.md).
"""

from __future__ import annotations

import pathlib

# Prefer a vendored copy (baked into the image by the Dockerfile → works offline);
# fall back to a CDN for bare `streamlit run` during local dev.
_H2C = pathlib.Path(__file__).parent / "html2canvas.min.js"
if _H2C.exists():
    HTML2CANVAS_TAG = f"<script>{_H2C.read_text()}</script>"
else:
    HTML2CANVAS_TAG = (
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/'
        'html2canvas.min.js"></script>'
    )


def widget_html(public_api_url: str) -> str:
    """Return the full HTML/JS for the bug-reporter widget, pointed at the given
    browser-reachable API base URL (e.g. http://localhost:8000)."""
    return (
        HTML2CANVAS_TAG
        # NOTE: raw string — the JS below contains escape sequences like "\n" that
        # must reach the browser verbatim. A normal string would turn "\n" into a
        # real newline, splitting a JS string literal across lines and breaking the
        # entire <script> (so nothing would work).
        + r"""
<style>
  * { box-sizing: border-box; }
  #app {
    font-family: -apple-system, Segoe UI, Roboto, sans-serif;
    background: #0f1116; color: #e7e7ea; padding: 22px; border-radius: 14px;
    min-height: 520px;
  }
  #app h1 { font-size: 22px; margin: 0 0 4px; }
  #app .sub { color: #9aa0aa; font-size: 13px; margin-bottom: 18px; }
  .cards { display: flex; gap: 14px; margin-bottom: 20px; flex-wrap: wrap; }
  .card {
    flex: 1 1 150px; background: #1a1d25; border: 1px solid #262a34;
    border-radius: 12px; padding: 16px;
  }
  .card .k { color: #9aa0aa; font-size: 12px; }
  .card .v { font-size: 26px; font-weight: 700; margin-top: 4px; }
  .card .d { font-size: 12px; margin-top: 2px; }
  .up { color: #46c46e; } .down { color: #e5484d; }
  table { width: 100%; border-collapse: collapse; background: #1a1d25;
          border-radius: 12px; overflow: hidden; }
  th, td { text-align: left; padding: 11px 14px; font-size: 14px;
           border-bottom: 1px solid #262a34; }
  th { color: #9aa0aa; font-weight: 600; }
  .hint { margin-top: 16px; font-size: 13px; color: #9aa0aa; }
  .pill { padding: 2px 9px; border-radius: 999px; font-size: 12px; }
  .live { background: #143d24; color: #46c46e; }
  .offer { background: #3d2f14; color: #e0b040; }

  /* Floating ladybug FAB */
  #fab {
    position: fixed; bottom: 24px; right: 24px; width: 58px; height: 58px;
    border-radius: 50%; background: #e5484d; color: #fff; font-size: 26px;
    border: none; cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.45);
    z-index: 900;
  }
  #fab:hover { background: #d13438; }

  /* Editor overlay */
  #editor {
    position: fixed; inset: 0; background: rgba(6,8,12,.9); z-index: 1000;
    display: none; align-items: flex-start; justify-content: center;
    overflow: auto; padding: 18px;
  }
  #editor .panel {
    background: #14171d; border: 1px solid #262a34; border-radius: 14px;
    padding: 18px; width: 100%; max-width: 560px;
    font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: #e7e7ea;
  }
  #editor h3 { margin: 0 0 4px; font-size: 18px; }
  #editor .note { color: #9aa0aa; font-size: 13px; margin-bottom: 12px; }
  #canvas-wrap { position: relative; border: 1px solid #262a34; border-radius: 10px;
                 overflow: auto; background: #000; text-align: center; max-height: 320px; }
  /* Cap the *display* height so the form + Send button stay in view; the canvas
     keeps its full resolution for the uploaded blob. max-width/height preserve aspect. */
  #draw { display: block; margin: 0 auto; max-width: 100%; max-height: 300px;
          touch-action: none; cursor: crosshair; }
  .row { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  .cat {
    flex: 1 1 30%; padding: 9px; border-radius: 9px; border: 1px solid #2c313c;
    background: #1a1d25; color: #cfd3da; cursor: pointer; font-size: 14px; text-align: center;
  }
  .cat.active { color: #fff; border-color: transparent; }
  .cat.active.bug { background: #e5484d; }
  .cat.active.idea { background: #3b82f6; }
  .cat.active.improvement { background: #e0b040; color: #1a1d25; }
  #editor input, #editor textarea {
    width: 100%; margin-top: 10px; padding: 10px; border-radius: 9px;
    border: 1px solid #2c313c; background: #1a1d25; color: #fff; font-size: 14px;
  }
  #editor textarea { min-height: 74px; resize: vertical; }
  .btns { display: flex; gap: 10px; margin-top: 14px; }
  .btn { flex: 1; padding: 12px; border-radius: 10px; border: none; cursor: pointer;
         font-size: 15px; font-weight: 600; }
  .btn.primary { background: #46c46e; color: #06240f; }
  .btn.primary:disabled { opacity: .45; cursor: not-allowed; }
  .btn.ghost { background: #232833; color: #cfd3da; }
  .btn.tool { flex: none; padding: 8px 12px; background: #232833; color: #cfd3da;
              font-size: 13px; font-weight: 500; }
  #result { margin-top: 12px; font-size: 14px; }
  #result a { color: #6ea8fe; }
</style>

<div id="app">
  <h1>🏠 Acme Estates — Agent Dashboard</h1>
  <div class="sub">Mock host application. Tap the red 🐞 (bottom-right) to report a problem on this screen.</div>
  <div class="cards">
    <div class="card"><div class="k">Active listings</div><div class="v">128</div><div class="d up">+4 this week</div></div>
    <div class="card"><div class="k">Leads this week</div><div class="v">37</div><div class="d up">+12%</div></div>
    <div class="card"><div class="k">Viewings booked</div><div class="v">9</div><div class="d down">-2</div></div>
  </div>
  <table>
    <thead><tr><th>Address</th><th>Price</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>12 Oak St</td><td>£450k</td><td><span class="pill live">Live</span></td></tr>
      <tr><td>5 Elm Ave</td><td>£620k</td><td><span class="pill offer">Under offer</span></td></tr>
      <tr><td>88 Pine Rd</td><td>£310k</td><td><span class="pill live">Live</span></td></tr>
    </tbody>
  </table>
  <div class="hint">👉 See something wrong? The bug button snapshots this exact screen so you can circle the problem.</div>
</div>

<button id="fab" title="Report a bug">🐞</button>

<div id="editor">
  <div class="panel">
    <h3>🐞 Report an issue</h3>
    <div class="note">Draw on the screenshot to mark the problem, then send. Goes straight to the auto-ticket service.</div>
    <div id="canvas-wrap"><canvas id="draw"></canvas></div>
    <div class="row">
      <button class="btn tool" id="undo">↩︎ Undo</button>
      <button class="btn tool" id="clear">Clear</button>
    </div>
    <div class="row">
      <div class="cat bug active" data-cat="bug">🐛 Bug</div>
      <div class="cat idea" data-cat="idea">💡 Idea</div>
      <div class="cat improvement" data-cat="improvement">🔧 Improvement</div>
    </div>
    <input id="title" placeholder="Short title (optional — taken from the description if blank)" />
    <textarea id="desc" placeholder="What happened / what should change?"></textarea>
    <div class="btns">
      <button class="btn ghost" id="cancel">Cancel</button>
      <button class="btn primary" id="send">Send</button>
    </div>
    <div id="result"></div>
  </div>
</div>

<script>
  const API = "__API_URL__";
  const $ = (id) => document.getElementById(id);
  let category = "bug";
  let strokes = [];        // list of point-arrays; enables undo
  let cur = null;
  let bg = null;           // captured screenshot (a canvas)
  const canvas = $("draw");
  const ctx = canvas.getContext("2d");

  // --- category chips ---
  document.querySelectorAll(".cat").forEach((el) => {
    el.onclick = () => {
      document.querySelectorAll(".cat").forEach((c) => c.classList.remove("active"));
      el.classList.add("active");
      category = el.dataset.cat;
    };
  });

  // --- open: capture screenshot, then show editor ---
  $("fab").onclick = async () => {
    $("fab").style.visibility = "hidden";
    try {
      bg = await html2canvas(document.getElementById("app"), { backgroundColor: "#0f1116", scale: 1 });
    } catch (e) {
      // Fallback: blank canvas the size of the app if html2canvas is unavailable.
      const el = document.getElementById("app").getBoundingClientRect();
      bg = document.createElement("canvas"); bg.width = el.width; bg.height = el.height;
      const bc = bg.getContext("2d"); bc.fillStyle = "#0f1116"; bc.fillRect(0, 0, bg.width, bg.height);
    } finally {
      $("fab").style.visibility = "visible";
    }
    canvas.width = bg.width; canvas.height = bg.height;
    strokes = []; redraw();
    $("result").innerHTML = "";
    $("editor").style.display = "flex";
  };

  // --- drawing (pointer events → mouse + touch) ---
  function pos(e) {
    const r = canvas.getBoundingClientRect();
    const sx = canvas.width / r.width, sy = canvas.height / r.height;
    return [(e.clientX - r.left) * sx, (e.clientY - r.top) * sy];
  }
  canvas.addEventListener("pointerdown", (e) => {
    cur = [pos(e)]; strokes.push(cur); canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!cur) return;
    cur.push(pos(e)); redraw();
  });
  const end = () => { cur = null; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (bg) ctx.drawImage(bg, 0, 0);
    ctx.lineJoin = ctx.lineCap = "round";
    ctx.strokeStyle = "rgba(229,72,77,0.55)";
    ctx.lineWidth = Math.max(6, canvas.width / 90);
    for (const s of strokes) {
      if (s.length < 2) {  // a tap → a dot
        ctx.fillStyle = "rgba(229,72,77,0.55)";
        ctx.beginPath(); ctx.arc(s[0][0], s[0][1], ctx.lineWidth / 2, 0, 7); ctx.fill();
        continue;
      }
      ctx.beginPath(); ctx.moveTo(s[0][0], s[0][1]);
      for (let i = 1; i < s.length; i++) ctx.lineTo(s[i][0], s[i][1]);
      ctx.stroke();
    }
  }

  $("undo").onclick = () => { strokes.pop(); redraw(); };
  $("clear").onclick = () => { strokes = []; redraw(); };
  $("cancel").onclick = () => { $("editor").style.display = "none"; };

  // --- send: composite (already on canvas) → POST to the service ---
  $("send").onclick = () => {
    const btn = $("send");
    // Title is optional — derive one so Send is never blocked.
    const title = $("title").value.trim()
      || $("desc").value.trim().split("\n")[0].slice(0, 80)
      || "Bug report from the demo UI";
    const body = $("desc").value;
    const meta = { screen: "Dashboard", annotated: strokes.length > 0 };

    btn.disabled = true; btn.textContent = "Sending…"; $("result").textContent = "";

    const done = (d) => {
      const link = d && d.github_url
        ? ' <a href="' + d.github_url + '" target="_blank">' + (d.github_number ? "#" + d.github_number : "view") + "</a>"
        : "";
      $("result").innerHTML = "✅ Sent — issue raised." + link + " Open the Issues feed tab and Refresh.";
      $("result").scrollIntoView({ block: "nearest" });
      btn.textContent = "Sent ✓";
      setTimeout(() => { $("editor").style.display = "none"; btn.disabled = false; btn.textContent = "Send"; }, 2400);
    };
    const fail = (err) => {
      console.error("[bug-reporter] send failed:", err);
      $("result").innerHTML = "⚠️ Could not send: " + err + " — API at " + API +
        ". Check the browser console + that the api container is up.";
      $("result").scrollIntoView({ block: "nearest" });
      btn.disabled = false; btn.textContent = "Send";
    };

    // No-screenshot fallback keeps the report working even if the canvas can't
    // produce a blob (e.g. tainted canvas / toBlob unsupported).
    const postText = () =>
      fetch(API + "/tickets", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, body, category, source: "streamlit-demo", meta }),
      }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(done).catch(fail);

    try {
      canvas.toBlob((blob) => {
        if (!blob) { postText(); return; }
        const fd = new FormData();
        fd.append("title", title); fd.append("body", body);
        fd.append("category", category); fd.append("source", "streamlit-demo");
        fd.append("meta", JSON.stringify(meta));
        fd.append("screenshot", blob, "annotated.png");
        fetch(API + "/tickets/multipart", { method: "POST", body: fd })
          .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then(done).catch(fail);
      }, "image/png");
    } catch (e) {
      postText();  // toBlob threw (tainted canvas) — send text-only
    }
  };
</script>
""".replace("__API_URL__", public_api_url.rstrip("/"))
    )
