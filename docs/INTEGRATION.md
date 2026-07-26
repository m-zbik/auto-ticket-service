# Integration Guide — add the 🐞 bug icon to your project

The auto-ticket service is deliberately transport-agnostic: **any UI or backend that
can make an HTTP request can raise a ticket.** This guide shows how to (1) drop a
floating bug icon into common frontends, (2) call the service from a backend, and
(3) poll for newly filed issues.

The only endpoint you strictly need is:

```
POST {API_URL}/tickets
{ "title": "...", "body": "...", "category": "bug", "source": "your-app", "meta": {...} }
```

Set `API_URL` from an environment/config value — never hardcode the host.

---

## The pattern

Every integration is the same three steps:

1. **Render a floating bug icon** on every screen (fixed position, bottom/top corner).
2. **On click, collect** a short form — category, title, description, optional screenshot — plus context you already have (current route, app version, user).
3. **POST it** to `{API_URL}/tickets` (or `/tickets/multipart` with a file) and show the returned issue link.

---

## React / Next.js

```tsx
// BugReporter.tsx
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_TICKET_API!; // e.g. https://tickets.internal

export function BugReporter({ source = "web-app" }: { source?: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("bug");
  const [sent, setSent] = useState<string | null>(null);

  async function submit() {
    const res = await fetch(`${API_URL}/tickets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title, body, category, source,
        meta: { route: window.location.pathname, app_version: "1.0.0" },
      }),
    });
    const data = await res.json();
    setSent(data.github_url ?? "stored");
  }

  return (
    <>
      {/* Floating bug icon — same idea as the iOS ladybug button */}
      <button
        onClick={() => setOpen(true)}
        style={{
          position: "fixed", bottom: 24, right: 24, width: 56, height: 56,
          borderRadius: "50%", background: "#e5484d", color: "#fff",
          fontSize: 24, border: "none", boxShadow: "0 6px 20px rgba(0,0,0,.35)",
          cursor: "pointer", zIndex: 1000,
        }}
        aria-label="Report a bug"
      >🐞</button>

      {open && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.4)", zIndex: 1001 }}
             onClick={() => setOpen(false)}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ maxWidth: 420, margin: "10vh auto", background: "#fff", padding: 20, borderRadius: 12 }}>
            <h3>🐞 Report an issue</h3>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="bug">🐛 Bug</option>
              <option value="idea">💡 Idea</option>
              <option value="improvement">🔧 Improvement</option>
            </select>
            <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <textarea placeholder="What happened?" value={body} onChange={(e) => setBody(e.target.value)} />
            <button disabled={!title} onClick={submit}>Send</button>
            {sent && <p>Thanks! {sent.startsWith("http") ? <a href={sent}>View issue</a> : sent}</p>}
          </div>
        </div>
      )}
    </>
  );
}
```

Mount `<BugReporter source="web-app" />` once in your root layout and it appears on every page.

---

## Plain HTML / vanilla JS

Drop this at the end of `<body>` on any page:

```html
<button id="bug-fab" title="Report a bug"
  style="position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;
         background:#e5484d;color:#fff;font-size:24px;border:none;cursor:pointer;
         box-shadow:0 6px 20px rgba(0,0,0,.35);z-index:1000">🐞</button>
<script>
  const API_URL = "http://localhost:8000"; // set to your service
  document.getElementById("bug-fab").onclick = async () => {
    const title = prompt("Describe the bug (short title):");
    if (!title) return;
    const res = await fetch(`${API_URL}/tickets`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title, category: "bug", source: "website",
        meta: { route: location.pathname, ua: navigator.userAgent },
      }),
    });
    const d = await res.json();
    alert(d.github_url ? "Reported: " + d.github_url : "Reported (stored).");
  };
</script>
```

---

## iOS / SwiftUI

This service is the backend the iOS ladybug button was extracted from. A `.withBugReporter()`
view modifier reproduces it — a floating `ladybug.fill` icon that captures a screenshot,
shows a form, and uploads via the multipart endpoint:

```swift
// POST a report (multipart so we can attach the screenshot)
func sendTicket(title: String, body: String, category: String,
                screenshot: UIImage?) async throws {
    let apiURL = ProcessInfo.processInfo.environment["TICKET_API"] ?? "http://localhost:8000"
    let boundary = UUID().uuidString
    var req = URLRequest(url: URL(string: "\(apiURL)/tickets/multipart")!)
    req.httpMethod = "POST"
    req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

    var data = Data()
    let fields = ["title": title, "body": body, "category": category,
                  "source": "ios-app", "meta": #"{"screen":"Dashboard"}"#]
    for (k, v) in fields {
        data.append("--\(boundary)\r\n".data(using: .utf8)!)
        data.append("Content-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n".data(using: .utf8)!)
    }
    if let img = screenshot, let jpeg = img.jpegData(compressionQuality: 0.7) {
        data.append("--\(boundary)\r\n".data(using: .utf8)!)
        data.append("Content-Disposition: form-data; name=\"screenshot\"; filename=\"s.jpg\"\r\n".data(using: .utf8)!)
        data.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
        data.append(jpeg); data.append("\r\n".data(using: .utf8)!)
    }
    data.append("--\(boundary)--\r\n".data(using: .utf8)!)
    req.httpBody = data
    _ = try await URLSession.shared.data(for: req)
}
```

The floating-button UX (a `ViewModifier` that overlays a `ladybug.fill` icon and
presents the form) is exactly the iOS `FeedbackButton`/`FeedbackFormView` pattern.

---

## Screenshot + annotate (the iOS-style flow)

The most useful reports include a **screenshot with the problem circled** — the iOS
app captures the screen and lets the user draw on it (PencilKit marker) before
sending. You can do the same on the web with zero manual upload:

1. On bug-icon click, capture the current screen with **[html2canvas](https://html2canvas.hertzen.com/)** (`html2canvas(document.body)`), which renders the DOM to a `<canvas>`.
2. Show that canvas in an overlay and let the user **draw** on it (freehand strokes via Pointer Events — works for mouse and touch).
3. `canvas.toBlob(...)` the composited image and POST it to `/tickets/multipart` as the `screenshot` field. **No file picker.**

A complete, framework-free implementation is in **[`ui/bug_widget.py`](../ui/bug_widget.py)** —
it's plain HTML/JS you can lift into any host page. The core send:

```js
canvas.toBlob((blob) => {
  const fd = new FormData();
  fd.append("title", title);
  fd.append("body", description);
  fd.append("category", category);          // bug | idea | improvement
  fd.append("source", "web-app");
  fd.append("meta", JSON.stringify({ screen: location.pathname, annotated: true }));
  fd.append("screenshot", blob, "annotated.png");
  fetch(`${API_URL}/tickets/multipart`, { method: "POST", body: fd });
}, "image/png");
```

> **Note (Streamlit specifics):** a Streamlit component runs in a sandboxed iframe and
> can't screenshot the host page, so the demo widget renders the mock app screen
> *inside itself* and captures that. In a normal web app (React, plain HTML, etc.)
> html2canvas captures the real page directly. Also pass a **browser-reachable** API
> URL (e.g. `http://localhost:8000`), not an internal Docker hostname.

## From a backend (server-to-server)

Anything server-side can raise tickets too — e.g. turn an unhandled exception into an issue.

**Python**

```python
import httpx

def raise_ticket(title, body, source="backend", **meta):
    httpx.post("http://auto-ticket-api:8000/tickets", json={
        "title": title, "body": body, "category": "bug",
        "source": source, "meta": meta,
    }, timeout=10)

# e.g. in an exception handler
raise_ticket("Unhandled 500 in /checkout", str(exc),
             source="orders-svc", request_id=req_id)
```

**Node**

```js
await fetch(`${process.env.TICKET_API}/tickets`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title, body, category: "bug", source: "orders-svc", meta: { requestId } }),
});
```

---

## Auto-check for new issues (polling)

To show a "new issues" badge or feed in your own dashboard, poll `GET /tickets/new`
with the timestamp of your last check. The service's background poller keeps Postgres
in sync with GitHub, so this returns issues opened *anywhere* — via this service or
directly on GitHub.

```js
let lastSeen = new Date().toISOString();

async function checkNewIssues() {
  const res = await fetch(`${API_URL}/tickets/new?since=${encodeURIComponent(lastSeen)}`);
  const { count, tickets } = await res.json();
  if (count > 0) {
    showBadge(count);            // e.g. "🆕 3"
    lastSeen = new Date().toISOString();
  }
}
setInterval(checkNewIssues, 30_000);
```

Tune how fast the service itself syncs with `POLL_INTERVAL_SECONDS` (default 60s), or
trigger an immediate sync with `POST /tickets/sync`.

---

## Checklist for a new project

- [ ] Deploy the service (`docker compose up`, or just the `api` + `db` services) reachable from your app.
- [ ] Set `MOCK_GITHUB=false`, `GITHUB_TOKEN`, `GITHUB_REPO` for real issues.
- [ ] Set `CORS_ORIGINS` to your UI's origin (not `*`) if the browser calls it directly.
- [ ] Add the floating bug icon using the snippet for your framework above.
- [ ] Pass a meaningful `source` and useful `meta` (route, version, user) so issues are triageable.
- [ ] (Optional) Poll `GET /tickets/new` to surface newly filed issues in-app.
