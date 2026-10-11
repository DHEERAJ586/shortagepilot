import pytest

from planner import (
    AT_RISK, CONTRACT_FIRST, ON_TIME, PARTIALLY_LATE, PENALTY_FIRST,
    build_plan, compare_plans, explain,
)
from validation import apply_shipment_update


@pytest.fixture
def revised_shipments(shipments, sample_update, planning_date):
    return apply_shipment_update(shipments, sample_update, planning_date)


def plan(inventory, orders, shipments, policy, planning_date):
    return build_plan(inventory, orders, shipments, policy, planning_date)


def alloc_map(result):
    return {(r.date, r.order_id): r.quantity for r in result.allocations.itertuples()}


@pytest.mark.parametrize("policy", [CONTRACT_FIRST, PENALTY_FIRST])
def test_baseline_everything_on_time(inventory, orders, shipments, planning_date, policy):
    r = plan(inventory, orders, shipments, policy, planning_date)
    t = r.totals
    assert t["demand"] == 150
    assert t["supply"] == 150
    assert t["late_qty"] == 0
    assert t["unfulfilled_qty"] == 0
    assert t["penalty"] == 0
    assert t["contractual_at_risk"] == 0


def test_revised_contract_first(inventory, orders, revised_shipments, planning_date):
    r = plan(inventory, orders, revised_shipments, CONTRACT_FIRST, planning_date)
    assert alloc_map(r) == {
        ("2026-10-11", "ORD-101"): 60,
        ("2026-10-11", "ORD-102"): 40,
        ("2026-10-13", "ORD-102"): 10,
        ("2026-10-13", "ORD-103"): 20,
        ("2026-10-15", "ORD-103"): 20,
    }
    o = r.orders.set_index("order_id")
    assert o.loc["ORD-102", "late_qty"] == 10
    assert o.loc["ORD-102", "penalty"] == 3000
    assert o.loc["ORD-101", "late_qty"] == 0 and not o.loc["ORD-101", "contractual_shortfall"]
    assert o.loc["ORD-103", "late_qty"] == 0
    assert o.loc["ORD-102", "status"] == PARTIALLY_LATE
    assert r.totals["penalty"] == 3000
    assert r.totals["contractual_at_risk"] == 0


def test_revised_penalty_first(inventory, orders, revised_shipments, planning_date):
    r = plan(inventory, orders, revised_shipments, PENALTY_FIRST, planning_date)
    assert alloc_map(r) == {
        ("2026-10-11", "ORD-102"): 50,
        ("2026-10-11", "ORD-101"): 50,
        ("2026-10-13", "ORD-101"): 10,
        ("2026-10-13", "ORD-103"): 20,
        ("2026-10-15", "ORD-103"): 20,
    }
    o = r.orders.set_index("order_id")
    assert o.loc["ORD-102", "late_qty"] == 0
    assert o.loc["ORD-101", "late_qty"] == 10
    assert o.loc["ORD-101", "late_delivered_qty"] == 10
    assert o.loc["ORD-101", "penalty"] == 0  # no per-unit penalty specified for Atlas
    assert o.loc["ORD-101", "contractual_shortfall"]  # but the contractual shortfall is flagged
    assert r.totals["penalty"] == 0
    assert r.totals["contractual_at_risk"] == 1


def test_late_labels_on_allocations(inventory, orders, revised_shipments, planning_date):
    r = plan(inventory, orders, revised_shipments, CONTRACT_FIRST, planning_date)
    late = r.allocations[r.allocations["timing"] == "Late"]
    assert list(late["order_id"]) == ["ORD-102"] and list(late["quantity"]) == [10]


def test_at_risk_status_means_zero_slack(inventory, orders, shipments, planning_date):
    r = plan(inventory, orders, shipments, CONTRACT_FIRST, planning_date)
    o = r.orders.set_index("order_id")
    assert o.loc["ORD-101", "status"] == ON_TIME  # served from stock on hand
    assert o.loc["ORD-102", "status"] == AT_RISK  # last 10 units land on its due date


def test_deterministic(inventory, orders, revised_shipments, planning_date):
    a = plan(inventory, orders, revised_shipments, CONTRACT_FIRST, planning_date)
    b = plan(inventory, orders, revised_shipments, CONTRACT_FIRST, planning_date)
    assert a.allocations.equals(b.allocations)
    assert a.orders.equals(b.orders)


@pytest.mark.parametrize("policy", [CONTRACT_FIRST, PENALTY_FIRST])
@pytest.mark.parametrize("which", ["baseline", "revised"])
def test_conservation_invariants(
    inventory, orders, shipments, revised_shipments, planning_date, policy, which
):
    ships = shipments if which == "baseline" else revised_shipments
    r = plan(inventory, orders, ships, policy, planning_date)
    supply_by_date = r.supply.groupby("date")["quantity"].sum()
    alloc_by_date = r.allocations.groupby("date")["quantity"].sum()
    for d, qty in alloc_by_date.items():
        assert qty <= supply_by_date[d]
    for row in r.orders.itertuples():
        assert 0 <= row.on_time_qty + row.late_delivered_qty <= row.quantity
        assert row.unfulfilled_qty >= 0
    assert r.totals["allocated"] <= r.totals["supply"]


def test_shortage_reported_as_unfulfilled(inventory, orders, shipments, planning_date):
    short = shipments.assign(quantity=[20])  # only 120 units of supply for 150 demand
    r = plan(inventory, orders, short, CONTRACT_FIRST, planning_date)
    assert r.totals["unfulfilled_qty"] == 30
    assert any("unfulfilled" in n for n in r.notes)


def test_cancelled_shipment_provides_no_supply(inventory, orders, shipments, planning_date):
    r = plan(inventory, orders, shipments.assign(status=["cancelled"]), CONTRACT_FIRST, planning_date)
    assert r.totals["supply"] == 100


def test_unknown_policy_rejected(inventory, orders, shipments, planning_date):
    with pytest.raises(ValueError):
        plan(inventory, orders, shipments, "cheapest", planning_date)


def test_compare_and_explain(inventory, orders, shipments, revised_shipments, planning_date):
    base = plan(inventory, orders, shipments, CONTRACT_FIRST, planning_date)
    rev = plan(inventory, orders, revised_shipments, CONTRACT_FIRST, planning_date)
    alt = plan(inventory, orders, revised_shipments, PENALTY_FIRST, planning_date)
    cmp = compare_plans(base, rev).set_index("order_id")
    assert cmp.loc["ORD-102", "delta_penalty"] == 3000
    assert cmp.loc["ORD-101", "delta_late_qty"] == 0
    text = " ".join(explain(base, rev, alt))
    assert "₹3,000" in text and "Beacon Electrical" in text and "Trade-off" in text
    assert "shipment SH-77" in text
