import io

import pandas as pd
import pytest

from validation import (
    Batch, ShipmentUpdate, ValidationError, apply_shipment_update, validate_inventory,
    validate_orders, validate_shipments, validate_update,
)


def csv(text):
    return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)


def update(batches, sid="SH-77", pid="CAP-001", **kw):
    return ShipmentUpdate(sid, pid, [Batch(q, d) for q, d in batches], **kw)


# ---- supplier update validation

def test_valid_update(shipments, sample_update, planning_date):
    check = validate_update(sample_update, shipments, planning_date)
    assert check.ok and not check.warnings


def test_unknown_shipment_cannot_be_applied(shipments):
    u = update([(30, "2026-10-13"), (20, "2026-10-15")], sid="SH-99")
    assert any("does not exist" in e for e in validate_update(u, shipments).errors)
    with pytest.raises(ValidationError):
        apply_shipment_update(shipments, u)


def test_product_mismatch_rejected(shipments):
    u = update([(50, "2026-10-13")], pid="RES-009")
    assert any("does not match" in e for e in validate_update(u, shipments).errors)


@pytest.mark.parametrize("bad", ["2026-13-45", "13 October 2026", "2026-10-1", "", None, "20261013"])
def test_invalid_date_rejected(shipments, bad):
    u = update([(30, "2026-10-13"), (20, bad)])
    check = validate_update(u, shipments)
    assert not check.ok and any("valid YYYY-MM-DD" in e for e in check.errors)
    with pytest.raises(ValidationError):
        apply_shipment_update(shipments, u)


def test_batches_must_sum_to_scheduled_quantity(shipments):
    u = update([(30, "2026-10-13"), (10, "2026-10-15")])
    check = validate_update(u, shipments)
    assert any("sum to 40" in e and "50" in e for e in check.errors)
    with pytest.raises(ValidationError):
        apply_shipment_update(shipments, u)


@pytest.mark.parametrize("bad", [-5, 0, 2.5, "abc", None, True])
def test_bad_quantities_rejected(shipments, bad):
    u = update([(bad, "2026-10-13"), (20, "2026-10-15")])
    assert any("positive whole number" in e for e in validate_update(u, shipments).errors)


def test_missing_required_facts(shipments):
    check = validate_update(ShipmentUpdate(), shipments)
    assert len(check.errors) >= 3


def test_warnings_do_not_block(shipments, planning_date):
    u = update([(30, "2026-10-13"), (20, "2026-10-15")], previous_eta_date="2026-10-01",
               needs_clarification=True, missing_fields=["supplier_id"])
    check = validate_update(u, shipments, planning_date)
    assert check.ok and len(check.warnings) == 3


def test_past_date_warns(shipments, planning_date):
    check = validate_update(update([(30, "2026-10-01"), (20, "2026-10-15")]), shipments, planning_date)
    assert check.ok and any("before the planning date" in w for w in check.warnings)


# ---- applying updates

def test_apply_replaces_schedule(shipments, sample_update):
    out = apply_shipment_update(shipments, sample_update)
    assert out[["quantity", "eta_date"]].values.tolist() == [[30, "2026-10-13"], [20, "2026-10-15"]]
    assert set(out["supplier_id"]) == {"SUP-01"} and set(out["status"]) == {"planned"}
    assert out["quantity"].sum() == 50
    assert shipments["quantity"].tolist() == [50]  # original untouched


def test_apply_is_idempotent(shipments, sample_update):
    once = apply_shipment_update(shipments, sample_update)
    twice = apply_shipment_update(once, sample_update)
    assert once.equals(twice) and twice["quantity"].sum() == 50


def test_apply_only_touches_target_shipment():
    ships = validate_shipments(csv(
        "shipment_id,supplier_id,product_id,quantity,eta_date,status\n"
        "SH-1,S,CAP-001,10,2026-10-12,planned\n"
        "SH-77,S,CAP-001,50,2026-10-12,planned\n"
        "SH-3,S,CAP-001,5,2026-10-14,planned\n"
    ))
    out = apply_shipment_update(ships, update([(25, "2026-10-13"), (25, "2026-10-15")]))
    assert out["shipment_id"].tolist() == ["SH-1", "SH-77", "SH-77", "SH-3"]
    assert out["quantity"].sum() == 65


# ---- CSV validation

def test_sample_style_csvs_validate(inventory, orders, shipments):
    assert inventory["on_hand_qty"].tolist() == [100]
    assert orders["contractual_priority"].tolist() == [True, False, False]
    assert orders["penalty_per_unit"].tolist() == [0, 300, 0]
    assert shipments["quantity"].tolist() == [50]


def test_missing_column():
    with pytest.raises(ValidationError, match="missing required column"):
        validate_inventory(csv("product_id,on_hand_qty\nA,1\n"))


def test_negative_and_invalid_values_reported_together():
    df = csv(
        "order_id,customer_name,product_id,quantity,due_date,contractual_priority,penalty_per_unit\n"
        "O1,A,P,-5,2026-10-12,true,0\n"
        "O2,B,P,ten,2026-13-12,maybe,-1\n"
    )
    errs = " | ".join(pytest.raises(ValidationError, validate_orders, df).value.errors)
    for expected in ["must be positive", "whole number", "valid YYYY-MM-DD", "true or false", "non-negative"]:
        assert expected in errs


def test_missing_values_not_zeroed():
    df = csv("product_id,product_name,on_hand_qty,as_of_date\nA,Thing,,2026-10-11\n")
    with pytest.raises(ValidationError, match="'on_hand_qty' is missing"):
        validate_inventory(df)


def test_duplicate_ids_rejected():
    inv = csv("product_id,product_name,on_hand_qty,as_of_date\nA,X,1,2026-10-11\nA,Y,2,2026-10-11\n")
    with pytest.raises(ValidationError, match="duplicate product_id"):
        validate_inventory(inv)
    ords = csv(
        "order_id,customer_name,product_id,quantity,due_date,contractual_priority,penalty_per_unit\n"
        "O1,A,P,1,2026-10-12,true,0\nO1,B,P,2,2026-10-12,false,0\n"
    )
    with pytest.raises(ValidationError, match="duplicate order_id"):
        validate_orders(ords)


def test_duplicate_shipment_row_rejected():
    df = csv(
        "shipment_id,supplier_id,product_id,quantity,eta_date,status\n"
        "SH-1,S,P,10,2026-10-12,planned\nSH-1,S,P,10,2026-10-12,planned\n"
    )
    with pytest.raises(ValidationError, match="double-count"):
        validate_shipments(df)


def test_multi_batch_shipment_is_valid():
    df = csv(
        "shipment_id,supplier_id,product_id,quantity,eta_date,status\n"
        "SH-1,S,P,30,2026-10-13,planned\nSH-1,S,P,20,2026-10-15,planned\n"
    )
    assert validate_shipments(df)["quantity"].sum() == 50
