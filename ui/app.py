"""Streamlit demo of the auto-ticket service.

Two parts:
  • Dashboard tab — a self-contained bug-reporter widget (see bug_widget.py): a
    mock app screen with a floating 🐞 button that screenshots the screen, lets you
    draw on it (like the iOS PencilKit marker), and sends it to the service. No
    file upload — the screenshot is captured, annotated, and POSTed in the browser.
  • Issues feed tab — reads tickets back from the service (server-side).

Everything is mock EXCEPT the calls to the service, which are real.
"""

from __future__ import annotations

import os

import requests
import streamlit as st
import streamlit.components.v1 as components

from bug_widget import widget_html

# Server-side base URL (this container → api container). Used for reads below.
API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
# Browser-facing base URL (the user's browser → the published API port). The bug
# widget runs in the browser, so it must use a host-reachable URL, not api:8000.
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Acme Estates — Demo", page_icon="🏠", layout="centered")


def api_health() -> dict | None:
    try:
        r = requests.get(f"{API_URL}/health", timeout=4)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None


health = api_health()
st.title("🐞 Auto-Ticket — live demo")
if health:
    mode = "🧪 mock GitHub" if health["mode"] == "mock" else f"✅ GitHub → {health['repo']}"
    st.caption(f"Service online · {mode} · {health['ticket_count']} tickets stored · browser posts to `{PUBLIC_API_URL}`")
else:
    st.error(f"Ticket service unreachable at {API_URL}. Is the `api` container up?")

tab_dash, tab_issues = st.tabs(["📊 Dashboard", "🆕 Issues feed"])

with tab_dash:
    st.write("Tap the red 🐞 button, mark the problem on the screenshot, and send:")
    components.html(widget_html(PUBLIC_API_URL), height=820, scrolling=True)

with tab_issues:
    st.subheader("Issues raised / discovered")
    st.caption("Filled by the background poller and by tickets you raise here.")
    c1, c2 = st.columns([1, 4])
    if c1.button("🔄 Refresh"):
        st.rerun()
    if c2.button("⚡ Force sync now"):
        try:
            res = requests.post(f"{API_URL}/tickets/sync", timeout=15).json()
            st.toast(f"Sync done — {res.get('new', 0)} new")
        except requests.RequestException as e:
            st.warning(f"Sync failed: {e}")

    try:
        tickets = requests.get(f"{API_URL}/tickets", timeout=6).json().get("tickets", [])
    except requests.RequestException:
        tickets = []

    if not tickets:
        st.info("No tickets yet. Raise one from the Dashboard tab with the 🐞 button.")
    for t in tickets:
        icon = {"bug": "🐛", "idea": "💡", "improvement": "🔧"}.get(t["category"], "📌")
        link = f" · [#{t['github_number']}]({t['github_url']})" if t.get("github_url") else ""
        with st.container(border=True):
            st.markdown(f"**{icon} {t['title']}**{link}")
            st.caption(f"{t['category']} · from `{t['source']}` · {t.get('created_at', '')[:19]}")
            if t.get("body"):
                st.write(t["body"])
            shot = t.get("screenshot_url")
            if shot:
                # Screenshots arrive as data: URIs — decode to bytes so st.image
                # renders them reliably. Guard against undecodable/corrupt images
                # (e.g. a non-image blob) so one bad ticket can't break the feed.
                try:
                    if shot.startswith("data:") and "base64," in shot:
                        import base64
                        st.image(base64.b64decode(shot.split("base64,", 1)[1]), width=320)
                    else:
                        st.image(shot, width=320)
                except Exception:
                    st.caption("🖼️ (screenshot attached — preview unavailable)")
