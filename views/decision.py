"""Screen 3: decision comparison, baseline vs revised, across both policies."""

import pandas as pd
import streamlit as st

import state
import ui
from planner import explain, money

ctx = state.context()
ui.header("decision", "Decision comparison", "What the supplier change does to late units, penalties and contractual commitments.")
policy = ui.policy_selector("decision")
base, rev, other = ctx.pair(policy)
bt, rt = base.totals, rev.totals

if not ctx.has_update:
    st.info("No supplier update applied yet: showing the baseline plan. Apply an update on the "
            "Supplier update screen to see the impact.")
    ui.next_step("supplier", "Go to Supplier update →")

lines = explain(base, rev, other if ctx.has_update else None)
summary = lines[0]
if rt["late_qty"] or rt["unfulfilled_qty"]:
    st.error(f"**Risk identified.** {summary}")
else:
    st.success(f"**No late units.** {summary}")

specs = [
    ("Late units", "late_qty", str, "Units not delivered by their due date, including units never delivered."),
    ("Known penalties", "penalty", money, "late units × per-unit penalty from the orders file."),
    ("Contractual late", "contractual_at_risk", str, "Contractual orders not fully delivered by their due date."),
    ("Undelivered", "unfulfilled_qty", str, "Units never delivered within the known supply."),
]
for col, (label, key, fmt, help_) in zip(st.columns(4), specs):
    delta = rt[key] - bt[key]
    if not ctx.has_update:
        shown_delta = None
    elif delta == 0:
        shown_delta = "no change vs baseline"
    else:
        shown_delta = ("+" if delta > 0 else "−") + fmt(abs(delta)) + " vs baseline"
    col.metric(label, fmt(rt[key]), help=help_, border=True, delta=shown_delta,
               delta_color="inverse" if delta else "off", delta_arrow="auto" if delta else "off")
for n in dict.fromkeys(rev.notes + base.notes):
    st.warning(n)
st.caption(f"Planning horizon ends {rev.horizon_end}. Penalty assumption: every unit not delivered by its due date "
           f"incurs the per-unit penalty; a later delivery does not erase it.")

c1, c2 = st.columns([2, 3], gap="large")
with c1:
    st.subheader("Supply by date")
    supply = pd.DataFrame({
        "Baseline schedule": base.supply.groupby("date")["quantity"].sum(),
        "Revised schedule": rev.supply.groupby("date")["quantity"].sum(),
    }).fillna(0).astype(int)
    supply.index.name = "Date"
    shown = supply if ctx.has_update else supply[["Baseline schedule"]]
    st.dataframe(shown, width="stretch")
with c2:
    st.caption("Units arriving per date: baseline vs revised schedule")
    st.bar_chart(shown, color=["#9aa5b1", "#1f6feb"] if ctx.has_update else ["#1f6feb"], height=240, stack=False)

st.subheader("Policy comparison")
st.dataframe(ui.policy_summary(ctx), hide_index=True, width="stretch",
             column_config={"Known penalty": st.column_config.NumberColumn(format="₹%.0f")})

st.subheader("What this means")
with st.container(border=True):
    for line in lines[1:]:
        st.markdown(f"- {line}")
    st.caption("Generated from fixed templates over the calculated results; no AI is involved.")

st.divider()
n1, n2 = st.columns(2)
with n1:
    ui.next_step("allocation", "Next: Allocation schedule →")
with n2:
    ui.next_step("orders", "Next: Orders & penalties →")
