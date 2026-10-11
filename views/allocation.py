"""Screen 4: date-by-date allocation schedule."""

import streamlit as st

import state
import ui

ctx = state.context()
ui.header("allocation", "Allocation schedule", "Who receives which units on which date, and whether they arrive on time.")
policy = ui.policy_selector("allocation")
base, rev, _ = ctx.pair(policy)

if not ctx.has_update:
    st.info("No supplier update applied yet: showing the baseline plan.")
tabs = st.tabs(["Revised plan", "Baseline plan"] if ctx.has_update else ["Baseline plan"])
for tab, plan in zip(tabs, [rev, base] if ctx.has_update else [base]):
    with tab:
        st.subheader("Delivery timeline by order")
        st.markdown(ui.delivery_grid(plan), unsafe_allow_html=True)
        st.subheader("Allocation by date and customer")
        st.dataframe(ui.allocation_schedule(plan), hide_index=True, width="stretch")
        with st.expander("Detailed allocation lines"):
            st.dataframe(plan.allocations, hide_index=True, width="stretch")
        t = plan.totals
        st.caption(f"{t['allocated']} of {t['supply']} supplied units allocated"
                   + (f"; {t['surplus']} units surplus." if t["surplus"] else "."))
