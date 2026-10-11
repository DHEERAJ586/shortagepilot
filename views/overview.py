"""Screen 1: planning data and the inventory / demand / incoming picture."""

import streamlit as st

import state
import ui
from planner import CONTRACT_FIRST
from validation import ValidationError, cross_check, validate_inventory, validate_orders, validate_shipments

ui.header("overview", "Overview", "Stock, customer demand and inbound supply before any supplier change.")

# --- data source (kept in session_state so other screens keep using it) -----------------
with st.expander("Data source", expanded=st.session_state.source_mode != "Sample data"):
    def sync_mode():
        st.session_state.source_mode = st.session_state.source_radio
        if st.session_state.source_mode == "Sample data":
            state.use_sample_dataset()

    modes = ["Sample data", "Upload CSVs"]
    st.radio("Data source", modes, index=modes.index(st.session_state.source_mode), horizontal=True,
             key="source_radio", on_change=sync_mode,
             help="Sample data is synthetic. Uploaded files must use the same column names as the samples.")
    if st.session_state.source_mode == "Upload CSVs":
        specs = [("inventory", "Inventory CSV", validate_inventory), ("orders", "Customer orders CSV", validate_orders),
                 ("shipments", "Inbound shipments CSV", validate_shipments)]
        tables, problems = [], []
        for col, (key, label, validator) in zip(st.columns(3), specs):
            f = col.file_uploader(label, type="csv", key=f"up_{key}")
            if f is None:
                problems.append(f"{label}: not uploaded yet.")
                continue
            try:
                tables.append(validator(state.read_csv(f)))
            except ValidationError as e:
                problems += [f"{label}: {m}" for m in e.errors]
            except Exception as e:
                problems.append(f"{label}: could not be read as CSV ({type(e).__name__}).")
        if problems:
            st.warning("Using the previous data until all three uploads are valid:\n\n" + "\n".join(f"- {p}" for p in problems))
        else:
            st.session_state.dataset = (*tables, "your uploaded CSVs")

ctx = state.context()
for w in cross_check(ctx.inventory, ctx.orders, ctx.base_ships):
    st.warning(w)

demand = int(ctx.orders["quantity"].sum())
on_hand = int(ctx.inventory["on_hand_qty"].sum())
active = ctx.base_ships[~ctx.base_ships["status"].str.lower().isin(state.INACTIVE)]
incoming = int(active["quantity"].sum())
cols = st.columns(5)
cards = [
    ("Stock on hand", on_hand, None),
    ("Customer demand", demand, None),
    ("Incoming stock", incoming, None),
    ("Stock gap", max(0, demand - on_hand), "Demand that stock on hand alone cannot cover (before any inbound shipment)."),
    ("Net shortage", max(0, demand - on_hand - incoming),
     "Demand still uncovered even if all inbound shipments arrive as originally planned (after inbound)."),
]
for col, (label, value, help_) in zip(cols, cards):
    col.metric(label, value, help=help_, border=True)
st.caption(f"Planning date **{ctx.planning_date}** · Loaded: {ctx.label}.")

base = ctx.plans[("baseline", CONTRACT_FIRST)]
t = base.totals
if t["late_qty"] == 0 and t["unfulfilled_qty"] == 0:
    st.success(f"Baseline outlook: all {t['demand']} units can be delivered by their due dates if inbound shipments "
               f"arrive as planned (Contract-first). Several orders still depend on supply landing on its due date.")
else:
    st.warning(f"Baseline outlook: {t['late_qty']} of {t['demand']} units already miss their due dates "
               f"(Contract-first), even before any supplier change.")

left, right = st.columns([3, 2])
with left:
    st.subheader("Customer orders")
    orders = ctx.orders.rename(columns={
        "order_id": "Order", "customer_name": "Customer", "product_id": "Product", "quantity": "Qty",
        "due_date": "Due", "contractual_priority": "Contractual", "penalty_per_unit": "₹/unit"})
    st.dataframe(orders, hide_index=True, width="stretch", column_config=ui.MONEY_CFG)
with right:
    st.subheader("Inbound shipments")
    st.dataframe(ctx.cur_ships, hide_index=True, width="stretch")
    if ctx.has_update:
        st.caption("Showing the revised schedule from the supplier update.")
st.subheader("Inventory")
st.dataframe(ctx.inventory, hide_index=True, width="stretch")

st.divider()
ui.next_step("supplier", "Next: enter a supplier update →")
