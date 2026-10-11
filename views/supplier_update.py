"""Screen 2: supplier message on the left, extracted shipment data to review on the right."""

import pandas as pd
import streamlit as st

import state
import ui
from ai_parser import ai_status, parse_supplier_update
from validation import (
    Batch, ShipmentUpdate, ValidationError, apply_shipment_update, parse_int, validate_update,
)

SAMPLE_MESSAGE = (
    "Shipment SH-77 for product CAP-001: Previous delivery date was 12 October 2026. "
    "Revised schedule: 30 units will arrive on 13 October 2026 and the remaining 20 units "
    "will arrive on 15 October 2026."
)
DEMO_UPDATE = ShipmentUpdate(
    shipment_id="SH-77",
    product_id="CAP-001",
    previous_eta_date="2026-10-12",
    new_batches=[Batch(30, "2026-10-13"), Batch(20, "2026-10-15")],
    change_type="reschedule_and_split",
    source_quote="30 units will arrive on 13 October 2026 and the remaining 20 units will arrive on 15 October 2026.",
)


def review_form(d: ShipmentUpdate, did: int) -> ShipmentUpdate:
    """Editable review form for a draft; returns the user's current values."""
    c1, c2 = st.columns(2)
    sid = c1.text_input("Shipment ID", d.shipment_id, key=f"sid_{did}")
    pid = c2.text_input("Product ID", d.product_id, key=f"pid_{did}")
    prev = st.text_input("Previous ETA stated in the message (YYYY-MM-DD)", d.previous_eta_date or "", key=f"prev_{did}")
    st.caption("New delivery batches (add or delete rows as needed)")
    frame = pd.DataFrame({
        "quantity": pd.to_numeric([b.quantity for b in d.new_batches], errors="coerce"),
        "eta_date": [str(b.eta_date) if b.eta_date else "" for b in d.new_batches],
    })
    edited = st.data_editor(
        frame, num_rows="dynamic", hide_index=True, key=f"batches_{did}", width="stretch",
        column_config={
            "quantity": st.column_config.NumberColumn("Quantity", step=1, format="%d"),
            "eta_date": st.column_config.TextColumn("Delivery date (YYYY-MM-DD)"),
        },
    )
    batches = []
    for r in edited.itertuples():
        qty = None if pd.isna(r.quantity) else (parse_int(r.quantity) if parse_int(r.quantity) is not None else float(r.quantity))
        date = r.eta_date.strip() if isinstance(r.eta_date, str) else ""
        if qty is None and not date:
            continue  # blank row
        batches.append(Batch(qty if qty is not None else "", date))
    return ShipmentUpdate(
        shipment_id=sid.strip(), product_id=pid.strip(), new_batches=batches,
        previous_eta_date=prev.strip() or None, change_type=d.change_type, source_quote=d.source_quote,
        confidence=d.confidence, missing_fields=d.missing_fields, needs_clarification=d.needs_clarification,
    )


st.session_state.setdefault("supplier_message", SAMPLE_MESSAGE)
ctx = state.context()
cfg = state.config()
available, reason = ai_status(cfg)

ui.header("supplier", "Supplier update", "Paste a supplier message, check what was extracted, and confirm before anything changes.")
if st.session_state.get("applied_msg"):
    st.success(st.session_state.pop("applied_msg"))
    ui.next_step("decision", "See the impact: Decision comparison →")

left, right = st.columns(2, gap="large")

# --- left: the message ------------------------------------------------------------------
with left:
    with st.container(border=True):
        st.markdown("#### Step 1 · Supplier message")

        def sync_message():
            st.session_state.supplier_message = st.session_state.supplier_message_widget

        message = st.text_area("Message", st.session_state.supplier_message, key="supplier_message_widget",
                               height=170, on_change=sync_message, label_visibility="collapsed")
        st.session_state.supplier_message = message
        used, limit = st.session_state.parse_count, cfg["max_parses"]
        limit_hit = used >= limit
        if st.button("Parse supplier update", type="primary", disabled=not available or limit_hit,
                     help="The only action that calls the DeepSeek API."):
            with st.spinner("Asking DeepSeek to extract the shipment schedule…"):
                result = parse_supplier_update(message, ctx.cur_ships, cache=st.session_state.parse_cache, config=cfg)
            if not result.from_cache:
                st.session_state.parse_count += 1  # counts every request that reached the API
            if result.update:
                state.set_draft(result.update, "ai", message)
                st.session_state.notice = ("Reused the earlier result for this exact message (no new API call)."
                                           if result.from_cache else "")
            else:
                st.session_state.parse_error = result.error
        if not available:
            st.info(f"{reason} AI parsing is off, but the planner works fully. Use manual entry below.")
        elif limit_hit:
            st.warning(f"AI parse limit reached for this session ({limit}). Use manual entry below, or reload the page.")
        elif st.session_state.parse_count:
            st.caption(f"AI parses used this session: {st.session_state.parse_count} of {limit}.")
        if st.session_state.parse_error:
            st.error(st.session_state.parse_error)
        if st.session_state.notice:
            st.caption(st.session_state.notice)

    with st.container(border=True):
        st.markdown("#### Manual entry")
        st.caption("Always available: use it if AI parsing is off or fails, or to start from scratch.")
        b1, b2 = st.columns(2)
        if b1.button("Enter update manually", width="stretch"):
            state.set_draft(ShipmentUpdate(new_batches=[Batch(None, ""), Batch(None, "")]), "manual", message)
        if b2.button("Load offline demo extraction", width="stretch",
                     help="Pre-fills the sample SH-77 update. Not produced by AI."):
            state.set_draft(DEMO_UPDATE, "demo", message)

    if ctx.has_update:
        st.markdown(ui.pill("Revised schedule applied", "warn"), unsafe_allow_html=True)
        if st.button("Reset to the original supplier schedule"):
            st.session_state.revised_ships = None
            st.rerun()

# --- right: extracted data ---------------------------------------------------------------
draft = st.session_state.draft
with right:
    with st.container(border=True):
        st.markdown("#### Step 2 · Extracted shipment data")
        if draft is None:
            st.markdown(ui.pill("Nothing to review", "idle"), unsafe_allow_html=True)
            st.caption("Parse the message or enter an update manually. The extracted facts appear here for "
                       "your review. Nothing changes until you confirm.")
        else:
            src = {"ai": "Extracted by AI", "demo": "Offline demo data (not AI)", "manual": "Entered manually"}[st.session_state.draft_source]
            st.markdown(ui.pill("Needs confirmation", "idle") + f" &nbsp;{src}. Nothing has been applied yet.",
                        unsafe_allow_html=True)
            if st.session_state.draft_message.strip() != st.session_state.supplier_message.strip():
                st.caption("Message this proposal came from:")
                st.info(st.session_state.draft_message or "(none)")
            if draft.source_quote:
                st.markdown(f"**Evidence quoted:** “{draft.source_quote}”")
            if draft.confidence is not None:
                st.caption(f"Extraction confidence indicator: {draft.confidence:.2f}. An uncalibrated model "
                           f"estimate, not a verified probability. Check the facts yourself.")

            proposal = review_form(draft, st.session_state.draft_id)
            check = validate_update(proposal, ctx.cur_ships, ctx.planning_date)
            for e in check.errors:
                st.error(e)
            for w in check.warnings:
                st.warning(w)
            if draft.missing_fields:
                st.warning("Missing fields reported: " + ", ".join(draft.missing_fields))

            st.markdown("#### Step 3 · Confirm")
            if check.ok:
                old = ctx.cur_ships[ctx.cur_ships["shipment_id"] == proposal.shipment_id]
                st.markdown(
                    "**Replaces:** " + ", ".join(f"{r.quantity} on {r.eta_date}" for r in old.itertuples())
                    + "  \n**With:** " + ", ".join(
                        f"{parse_int(b.quantity)} on {b.eta_date}"
                        for b in sorted(proposal.new_batches, key=lambda b: b.eta_date))
                )
            ack = True
            if check.ok and check.warnings:
                ack = st.checkbox("I have reviewed the warnings above and want to apply this update",
                                  key=f"ack_{st.session_state.draft_id}")
            a, b = st.columns(2)
            if a.button("Confirm and apply update", type="primary", disabled=not (check.ok and ack), width="stretch"):
                try:
                    st.session_state.revised_ships = apply_shipment_update(ctx.cur_ships, proposal, ctx.planning_date)
                except ValidationError as e:  # defence in depth; the button is disabled when invalid
                    st.error("; ".join(e.errors))
                else:
                    st.session_state.applied_msg = (
                        f"Applied: the schedule for {proposal.shipment_id} was replaced and the plan recalculated.")
                    state.clear_draft()
                    st.rerun()
            if b.button("Discard", width="stretch"):
                state.clear_draft()
                st.rerun()
