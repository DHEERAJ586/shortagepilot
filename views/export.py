"""Screen 6: CSV export of the allocation results."""

import pandas as pd
import streamlit as st

import state
import ui
from planner import POLICY_LABELS

ctx = state.context()
ui.header("export", "Export", "Download the allocation results to share or audit outside the app.")
policy = ui.policy_selector("export")
base, rev, _ = ctx.pair(policy)

scenarios = [("baseline", base), ("revised", rev)] if ctx.has_update else [("baseline", base)]
export = pd.concat([p.allocations.assign(scenario=s, policy=POLICY_LABELS[policy]) for s, p in scenarios])[
    ["scenario", "policy", "date", "order_id", "customer_name", "product_id", "source", "quantity", "due_date", "timing"]]

c1, c2 = st.columns(2)
c1.download_button("Download allocation results (CSV)", export.to_csv(index=False),
                   f"shortagepilot_allocations_{policy}.csv", "text/csv", type="primary", width="stretch")
c2.download_button("Download order outcomes (CSV)", rev.orders.to_csv(index=False),
                   f"shortagepilot_order_outcomes_{policy}.csv", "text/csv", width="stretch")
st.caption("Exports reflect the policy selected above"
           + (" and include both baseline and revised schedules." if ctx.has_update else
              " (baseline only; no supplier update applied)."))

st.subheader("Preview: allocation results")
st.dataframe(export, hide_index=True, width="stretch")
