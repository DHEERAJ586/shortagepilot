"""Deterministic, rule-based allocation planner.

No AI is involved here. Given starting stock, inbound supply batches and customer
orders, supply events are processed in date order and each event's units are handed
to the outstanding orders in policy order. This is a transparent priority heuristic,
not a globally optimal solution.

All dates are ISO ``YYYY-MM-DD`` strings (which sort correctly as text).
"""

from dataclasses import dataclass, field

import pandas as pd

CONTRACT_FIRST = "contract_first"
PENALTY_FIRST = "penalty_first"
POLICY_LABELS = {CONTRACT_FIRST: "Contract-first", PENALTY_FIRST: "Penalty-first"}

ON_HAND = "On hand"
# Shipments in these states no longer represent future supply.
INACTIVE_STATUSES = {"cancelled", "received"}

# Order statuses (planner output only; never set by the AI layer).
ON_TIME = "On time"
AT_RISK = "At risk"
PARTIALLY_LATE = "Partially late"
LATE = "Late"
UNFULFILLED = "Unfulfilled"


@dataclass
class _Order:
    order_id: str
    customer_name: str
    product_id: str
    quantity: int
    due_date: str
    contractual: bool
    penalty: float
    remaining: int = 0


@dataclass(frozen=True)
class SupplyEvent:
    date: str
    product_id: str
    quantity: int
    source: str  # ON_HAND or a shipment ID


@dataclass
class PlanResult:
    policy: str
    allocations: pd.DataFrame  # one row per (supply event, order) with units > 0
    orders: pd.DataFrame  # one row per order with fulfilment outcome
    supply: pd.DataFrame  # supply events used (date, product_id, source, quantity)
    horizon_end: str
    notes: list[str] = field(default_factory=list)

    @property
    def policy_label(self) -> str:
        return POLICY_LABELS[self.policy]

    @property
    def totals(self) -> dict:
        o = self.orders
        total_supply = int(self.supply["quantity"].sum()) if len(self.supply) else 0
        allocated = int(self.allocations["quantity"].sum()) if len(self.allocations) else 0
        return {
            "demand": int(o["quantity"].sum()),
            "supply": total_supply,
            "allocated": allocated,
            "surplus": total_supply - allocated,
            "on_time_qty": int(o["on_time_qty"].sum()),
            "late_delivered_qty": int(o["late_delivered_qty"].sum()),
            "unfulfilled_qty": int(o["unfulfilled_qty"].sum()),
            "late_qty": int(o["late_qty"].sum()),
            "penalty": float(o["penalty"].sum()),
            "contractual_at_risk": int(o["contractual_shortfall"].sum()),
            "contractual_units_late": int(o.loc[o["contractual_shortfall"], "late_qty"].sum()),
        }


def money(amount: float) -> str:
    return f"₹{amount:,.0f}" if float(amount).is_integer() else f"₹{amount:,.2f}"


def _policy_key(policy: str):
    if policy == CONTRACT_FIRST:
        return lambda o: (not o.contractual, o.due_date, -o.penalty, o.order_id)
    if policy == PENALTY_FIRST:
        return lambda o: (-o.penalty, o.due_date, not o.contractual, o.order_id)
    raise ValueError(f"Unknown allocation policy: {policy!r}")


def build_supply_events(
    inventory: pd.DataFrame, shipments: pd.DataFrame, planning_date: str
) -> tuple[list[SupplyEvent], list[str]]:
    """Starting stock lands on the planning date; each inbound batch lands on its ETA."""
    events: list[SupplyEvent] = []
    notes: list[str] = []
    for r in inventory.itertuples():
        if int(r.on_hand_qty) > 0:
            events.append(SupplyEvent(planning_date, r.product_id, int(r.on_hand_qty), ON_HAND))
    for r in shipments.itertuples():
        if str(r.status).lower() in INACTIVE_STATUSES:
            continue
        eta = r.eta_date
        if eta < planning_date:
            notes.append(
                f"Shipment {r.shipment_id} has an ETA ({eta}) before the planning date; "
                f"treated as available on {planning_date}."
            )
            eta = planning_date
        events.append(SupplyEvent(eta, r.product_id, int(r.quantity), r.shipment_id))
    events.sort(key=lambda e: (e.date, e.source != ON_HAND, e.source, e.product_id))
    return events, notes


def build_plan(
    inventory: pd.DataFrame,
    orders: pd.DataFrame,
    shipments: pd.DataFrame,
    policy: str,
    planning_date: str,
) -> PlanResult:
    """Allocate supply to orders under ``policy``. Pure function: same input, same output."""
    key = _policy_key(policy)
    events, notes = build_supply_events(inventory, shipments, planning_date)

    all_orders = [
        _Order(
            r.order_id,
            r.customer_name,
            r.product_id,
            int(r.quantity),
            r.due_date,
            bool(r.contractual_priority),
            float(r.penalty_per_unit),
            int(r.quantity),
        )
        for r in orders.itertuples()
    ]

    alloc_rows = []
    for ev in events:
        left = ev.quantity
        waiting = sorted(
            (o for o in all_orders if o.product_id == ev.product_id and o.remaining > 0), key=key
        )
        for o in waiting:
            if left == 0:
                break
            qty = min(left, o.remaining)
            o.remaining -= qty
            left -= qty
            alloc_rows.append(
                {
                    "date": ev.date,
                    "order_id": o.order_id,
                    "customer_name": o.customer_name,
                    "product_id": o.product_id,
                    "source": ev.source,
                    "quantity": qty,
                    "due_date": o.due_date,
                    "timing": "On time" if ev.date <= o.due_date else "Late",
                }
            )

    allocations = pd.DataFrame(
        alloc_rows,
        columns=[
            "date", "order_id", "customer_name", "product_id",
            "source", "quantity", "due_date", "timing",
        ],
    )
    supply = pd.DataFrame(
        [(e.date, e.product_id, e.source, e.quantity) for e in events],
        columns=["date", "product_id", "source", "quantity"],
    )

    order_rows = []
    for o in all_orders:
        mine = allocations[allocations["order_id"] == o.order_id]
        on_time = int(mine.loc[mine["timing"] == "On time", "quantity"].sum())
        late_delivered = int(mine.loc[mine["timing"] == "Late", "quantity"].sum())
        unfulfilled = o.quantity - on_time - late_delivered
        late_qty = o.quantity - on_time  # includes units never delivered
        # Zero slack: on time only because inbound supply lands on the due date itself.
        zero_slack = bool(
            ((mine["date"] == o.due_date) & (mine["source"] != ON_HAND)).any()
        )
        if unfulfilled > 0:
            status = UNFULFILLED
        elif late_delivered > 0:
            status = PARTIALLY_LATE if on_time > 0 else LATE
        elif zero_slack:
            status = AT_RISK
        else:
            status = ON_TIME
        order_rows.append(
            {
                "order_id": o.order_id,
                "customer_name": o.customer_name,
                "product_id": o.product_id,
                "quantity": o.quantity,
                "due_date": o.due_date,
                "contractual": o.contractual,
                "penalty_per_unit": o.penalty,
                "on_time_qty": on_time,
                "late_delivered_qty": late_delivered,
                "unfulfilled_qty": unfulfilled,
                "late_qty": late_qty,
                "penalty": late_qty * o.penalty,
                "contractual_shortfall": o.contractual and late_qty > 0,
                "last_delivery_date": mine["date"].max() if len(mine) else "",
                "status": status,
            }
        )
    order_df = pd.DataFrame(order_rows)

    dates = [o.due_date for o in all_orders] + [e.date for e in events]
    horizon_end = max(dates) if dates else planning_date
    result = PlanResult(policy, allocations, order_df, supply, horizon_end, notes)
    short = result.totals["unfulfilled_qty"]
    if short:
        notes.append(
            f"{short} units remain unfulfilled at the end of the planning horizon "
            f"({horizon_end}): known supply is insufficient."
        )
    return result


def compare_plans(baseline: PlanResult, revised: PlanResult) -> pd.DataFrame:
    """Per-order differences between two plans (same orders, same policy)."""
    b = baseline.orders.set_index("order_id")
    r = revised.orders.set_index("order_id")
    out = pd.DataFrame(
        {
            "customer_name": r["customer_name"],
            "baseline_status": b["status"],
            "revised_status": r["status"],
            "baseline_late_qty": b["late_qty"],
            "revised_late_qty": r["late_qty"],
            "baseline_penalty": b["penalty"],
            "revised_penalty": r["penalty"],
        }
    )
    out["delta_late_qty"] = out["revised_late_qty"] - out["baseline_late_qty"]
    out["delta_penalty"] = out["revised_penalty"] - out["baseline_penalty"]
    return out.reset_index()


def explain(
    baseline: PlanResult, revised: PlanResult, alternative: PlanResult | None = None
) -> list[str]:
    """Deterministic, template-based explanation of a plan. No LLM involved.

    ``alternative`` is the revised schedule under the other policy, used to describe
    the trade-off between policies.
    """
    t, bt = revised.totals, baseline.totals
    lines: list[str] = []

    if t["late_qty"] == 0:
        lines.append(
            f"Under {revised.policy_label}, all {t['demand']} units are delivered by their "
            f"due dates; no known late penalties."
        )
    else:
        lines.append(
            f"Under {revised.policy_label}, {t['late_qty']} of {t['demand']} units miss their due "
            f"dates, with known late penalties of {money(t['penalty'])} "
            f"(baseline schedule: {bt['late_qty']} late units, {money(bt['penalty'])})."
        )

    o = revised.orders
    for r in o[o["late_qty"] > 0].sort_values(["penalty", "order_id"], ascending=[False, True]).itertuples():
        parts = []
        if r.late_delivered_qty:
            parts.append(f"{r.late_delivered_qty} arrive late (last delivery {r.last_delivery_date})")
        if r.unfulfilled_qty:
            parts.append(f"{r.unfulfilled_qty} remain undelivered")
        lines.append(
            f"{r.customer_name} ({r.order_id}): {r.late_qty} of {r.quantity} units miss the "
            f"{r.due_date} deadline — {', '.join(parts)}. Known penalty {money(r.penalty)}."
        )

    at_risk = o[o["contractual_shortfall"]]
    if len(at_risk):
        names = ", ".join(f"{r.customer_name} ({r.late_qty} units)" for r in at_risk.itertuples())
        lines.append(f"Contractual commitment at risk: {names}.")
    elif o["contractual"].any():
        lines.append("All contractual commitments are met on time.")

    if alternative is not None and alternative.policy != revised.policy:
        at = alternative.totals
        if (at["penalty"], at["contractual_units_late"], at["late_qty"]) != (
            t["penalty"], t["contractual_units_late"], t["late_qty"],
        ):
            lines.append(
                f"Trade-off: under {alternative.policy_label}, known penalties would be "
                f"{money(at['penalty'])} (vs {money(t['penalty'])}), contractual units late "
                f"{at['contractual_units_late']} (vs {t['contractual_units_late']}), and total "
                f"late units {at['late_qty']} (vs {t['late_qty']})."
            )
        else:
            lines.append(f"{alternative.policy_label} gives the same outcome for this data.")

    lines.append(_next_action(revised))
    return lines


def _next_action(plan: PlanResult) -> str:
    t, o = plan.totals, plan.orders
    if t["unfulfilled_qty"] > 0:
        return (
            f"Suggested next action: known supply is {t['unfulfilled_qty']} units short. Ask suppliers "
            f"for additional supply and warn the affected customers."
        )
    if t["late_qty"] > 0:
        late_orders = o[o["late_qty"] > 0]
        sources = sorted(
            set(plan.allocations.loc[plan.allocations["timing"] == "Late", "source"]) - {ON_HAND}
        )
        who = ", ".join(late_orders["customer_name"])
        src = f"shipment {', '.join(sources)}" if sources else "the inbound supply"
        return (
            f"Suggested next action: ask the supplier whether {src} can be expedited so "
            f"{t['late_qty']} units arrive by {late_orders['due_date'].min()}, or notify {who} of the "
            f"revised delivery dates."
        )
    risky = o[o["status"] == AT_RISK]
    if len(risky):
        who = ", ".join(risky["customer_name"])
        return (
            f"Suggested next action: no late units, but {who} rely on inbound supply arriving on the due "
            f"date itself; monitor the supplier closely."
        )
    return "Suggested next action: none needed; monitor supplier updates."
