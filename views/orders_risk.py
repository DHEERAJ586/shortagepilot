"""Screen 5: order status, contractual risk and known late penalties."""

import streamlit as st

import state
import ui
from planner import compare_plans, money

ctx = state.context()
ui.header("orders", "Orders & penalties", "Which orders are late or at risk, and what the known penalties are.")
policy = ui.policy_selector("orders")
base, rev, _ = ctx.pair(policy)
rt, bt = rev.totals, base.totals

if rt["contractual_at_risk"]:
    names = ", ".join(rev.orders.loc[rev.orders["contractual_shortfall"], "customer_name"])
    st.error(f"Contractual commitment at risk: {names}.")
else:
    st.success("All contractual commitments are fully delivered by their due dates in this plan.")

st.subheader("Order status")
st.dataframe(ui.order_table(rev, base), hide_index=True, width="stretch", column_config=ui.MONEY_CFG)
st.caption("🟢 On time · 🟡 At risk (on time only if inbound supply lands exactly on the due date) · "
           "🟠 Partially late · 🔴 Late / Unfulfilled. Status comes from the planner, never from the AI.")

st.subheader("Known late-penalty summary")
late = rev.orders[rev.orders["late_qty"] > 0]
if late.empty:
    st.write("No late units, so no known penalties in this plan.")
else:
    summary = late[["customer_name", "late_qty", "penalty_per_unit", "penalty"]].rename(columns={
        "customer_name": "Customer", "late_qty": "Late units", "penalty_per_unit": "₹/unit", "penalty": "Known penalty"})
    st.dataframe(summary, hide_index=True, width="stretch", column_config=ui.MONEY_CFG)
    st.write(f"**Total known penalties: {money(rt['penalty'])}**"
             + (f" (baseline: {money(bt['penalty'])})" if ctx.has_update else ""))
    if (late["penalty_per_unit"] == 0).any():
        st.caption("Orders with ₹0/unit have no contractual penalty on file; their lateness still counts as late units.")

if ctx.has_update:
    st.subheader("Baseline vs revised, by order")
    cmp = compare_plans(base, rev).rename(columns={
        "order_id": "Order", "customer_name": "Customer", "baseline_status": "Baseline status",
        "revised_status": "Revised status", "baseline_late_qty": "Late (baseline)", "revised_late_qty": "Late (revised)",
        "baseline_penalty": "Penalty (baseline)", "revised_penalty": "Penalty (revised)",
        "delta_late_qty": "Δ late units", "delta_penalty": "Δ penalty"})
    st.dataframe(cmp, hide_index=True, width="stretch", column_config={
        k: st.column_config.NumberColumn(format="₹%.0f") for k in ("Penalty (baseline)", "Penalty (revised)", "Δ penalty")})
