"""Mock host app + floating bug icon — a Streamlit demo of the auto-ticket service.

This screen pretends to be "any UI" (here, a real-estate dashboard). Bolted onto
it is the reusable piece: a floating 🐞 bug icon (bottom-right, exactly like the
iOS ladybug button) that opens a report form and POSTs to the auto-ticket
service. A second tab shows the "new issues" feed the background poller fills.

Everything here is mock data EXCEPT the calls to the service — those are real
HTTP calls to the FastAPI app, which (in mock mode) simulates GitHub.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Acme Estates — Demo", page_icon="🏠", layout="wide")

# --- session state ----------------------------------------------------------
st.session_state.setdefault("show_report", False)
st.session_state.setdefault("last_seen", datetime.now(timezone.utc).isoformat())


# --- styling: turn a keyed Streamlit button into a floating round bug icon ----
# Streamlit tags an element that has a `key` with the CSS class `st-key-<key>`.
# We pin that wrapper to the bottom-right and restyle its button as a red circle,
# reproducing the iOS floating ladybug FAB.
st.markdown(
    """
    <style>
      .st-key-bug_fab {
          position: fixed; bottom: 28px; right: 28px; z-index: 1000;
      }
      .st-key-bug_fab button {
          width: 60px; height: 60px; border-radius: 50% !important;
          font-size: 26px !important; padding: 0 !important;
          background: #e5484d !important; color: white !important;
          border: none !important; box-shadow: 0 6px 20px rgba(0,0,0,.35);
      }
      .st-key-bug_fab button:hover { background: #d13438 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _api_health() -> dict | None:
    try:
        r = requests.get(f"{API_URL}/health", timeout=4)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None


def submit_ticket(title, body, category, reporter, screenshot) -> dict:
    """Real call to the auto-ticket service. Uses the multipart endpoint when a
    screenshot is attached, else the JSON endpoint."""
    if screenshot is not None:
        files = {"screenshot": (screenshot.name, screenshot.getvalue(), screenshot.type)}
        data = {
            "title": title, "body": body, "category": category,
            "source": "streamlit-demo", "reporter": reporter,
            "meta": '{"route": "/dashboard", "app_version": "demo-1.0"}',
        }
        r = requests.post(f"{API_URL}/tickets/multipart", data=data, files=files, timeout=20)
    else:
        payload = {
            "title": title, "body": body, "category": category,
            "source": "streamlit-demo", "reporter": reporter or None,
            "meta": {"route": "/dashboard", "app_version": "demo-1.0"},
        }
        r = requests.post(f"{API_URL}/tickets", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


# ===========================================================================
# Fake host-app content
# ===========================================================================
health = _api_health()

st.title("🏠 Acme Estates — Agent Dashboard")
st.caption("A mock host application. The bug icon (bottom-right) is the reusable auto-ticket widget.")

if health:
    mode = "🧪 mock GitHub" if health["mode"] == "mock" else f"✅ GitHub → {health['repo']}"
    st.success(f"Ticket service online · {mode} · {health['ticket_count']} tickets stored")
else:
    st.error(f"Ticket service unreachable at {API_URL}. Is the `api` container up?")

tab_dash, tab_issues = st.tabs(["📊 Dashboard", "🆕 Issues feed"])

with tab_dash:
    c1, c2, c3 = st.columns(3)
    c1.metric("Active listings", "128", "+4")
    c2.metric("Leads this week", "37", "+12%")
    c3.metric("Viewings booked", "9", "-2")
    st.divider()
    st.subheader("Recent listings")
    st.table({
        "Address": ["12 Oak St", "5 Elm Ave", "88 Pine Rd"],
        "Price": ["£450k", "£620k", "£310k"],
        "Status": ["Live", "Under offer", "Live"],
    })
    st.info("👉 Spot a problem on this screen? Tap the red 🐞 button at the bottom-right to report it.")

with tab_issues:
    st.subheader("Issues discovered / raised")
    st.caption("Filled by the service's background poller and by tickets you raise here.")
    cola, colb = st.columns([1, 4])
    if cola.button("🔄 Refresh"):
        st.rerun()
    if colb.button("⚡ Force sync now"):
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
        st.write("_No tickets yet. Raise one with the 🐞 button._")
    for t in tickets:
        icon = {"bug": "🐛", "idea": "💡", "improvement": "🔧"}.get(t["category"], "📌")
        link = f" · [#{t['github_number']}]({t['github_url']})" if t.get("github_url") else ""
        with st.container(border=True):
            st.markdown(f"**{icon} {t['title']}**{link}")
            st.caption(f"{t['category']} · from `{t['source']}` · {t.get('created_at', '')[:19]}")
            if t.get("body"):
                st.write(t["body"])
            if t.get("screenshot_url"):
                st.image(t["screenshot_url"], width=280)


# ===========================================================================
# Floating bug FAB + report form
# ===========================================================================
if st.button("🐞", key="bug_fab", help="Report a bug / idea"):
    st.session_state.show_report = True

if st.session_state.show_report:

    @st.dialog("🐞 Report an issue")
    def report_dialog():
        st.caption("Sent to the auto-ticket service, which opens a GitHub issue.")
        category = st.radio(
            "Category", ["bug", "idea", "improvement"],
            format_func=lambda c: {"bug": "🐛 Bug", "idea": "💡 Idea", "improvement": "🔧 Improvement"}[c],
            horizontal=True,
        )
        title = st.text_input("Title", placeholder="Login button does nothing")
        body = st.text_area("What happened / what should change?", height=120)
        reporter = st.text_input("Your email (optional)", placeholder="you@example.com")
        screenshot = st.file_uploader("Screenshot (optional)", type=["png", "jpg", "jpeg"])

        col1, col2 = st.columns(2)
        if col1.button("Cancel", use_container_width=True):
            st.session_state.show_report = False
            st.rerun()
        if col2.button("Send", type="primary", use_container_width=True, disabled=not title.strip()):
            try:
                res = submit_ticket(title.strip(), body, category, reporter, screenshot)
                st.session_state.show_report = False
                url = res.get("github_url")
                st.success("Thanks! Issue raised." + (f" [{url}]({url})" if url else ""))
                st.balloons()
            except requests.RequestException as e:
                st.error(f"Could not submit: {e}")

    report_dialog()
