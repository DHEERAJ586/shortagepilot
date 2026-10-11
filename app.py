"""ShortagePilot entry point. Run with:  streamlit run app.py

Each workflow step is its own screen under views/; shared state lives in state.py.
"""

import streamlit as st

import ui
from ai_parser import ai_status
import state

st.set_page_config(page_title="ShortagePilot", page_icon="🧭", layout="wide")
st.markdown(ui.css(), unsafe_allow_html=True)

try:
    state.init_state()
except Exception as e:  # missing/invalid sample files
    st.error(f"The sample data could not be loaded: {'; '.join(getattr(e, 'errors', [str(e)]))}")
    st.stop()

pages = {
    "overview": st.Page("views/overview.py", title="Overview", icon=":material/inventory_2:", default=True),
    "supplier": st.Page("views/supplier_update.py", title="Supplier update", icon=":material/mail:", url_path="supplier-update"),
    "decision": st.Page("views/decision.py", title="Decision comparison", icon=":material/compare_arrows:", url_path="decision"),
    "allocation": st.Page("views/allocation.py", title="Allocation schedule", icon=":material/calendar_month:", url_path="allocation"),
    "orders": st.Page("views/orders_risk.py", title="Orders & penalties", icon=":material/warning:", url_path="orders"),
    "export": st.Page("views/export.py", title="Export", icon=":material/download:", url_path="export"),
}
state.PAGES.clear()
state.PAGES.update(pages)
st.logo("assets/logo.svg", size="large")
nav = st.navigation(list(pages.values()), position="sidebar")

ctx = state.context()
available, _ = ai_status(state.config())
with st.sidebar:
    st.caption(f"Planning date **{ctx.planning_date}** · {ctx.label}")
    chips = [ui.pill("Revised schedule applied" if ctx.has_update else "Baseline schedule", "warn" if ctx.has_update else "ok")]
    if st.session_state.draft is not None:
        chips.append(ui.pill("Update needs confirmation", "idle"))
    chips.append(ui.pill("AI parsing on" if available else "AI parsing off (manual entry)", "ok" if available else "idle"))
    st.markdown("<br>".join(chips), unsafe_allow_html=True)
    st.caption("🌓 Dark mode: open the ⋮ menu (top right) and choose Dark, Light or System.")

nav.run()
