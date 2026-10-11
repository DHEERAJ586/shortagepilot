"""Input validation and the (only) code path that changes the inbound schedule.

CSV validators return cleaned DataFrames (dates as ISO strings, numbers as ints/floats,
booleans as bool) or raise ValidationError listing every problem found.
Shipment updates are validated here before ``apply_shipment_update`` will touch anything.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

INVENTORY_COLS = ["product_id", "product_name", "on_hand_qty", "as_of_date"]
ORDER_COLS = [
    "order_id", "customer_name", "product_id", "quantity",
    "due_date", "contractual_priority", "penalty_per_unit",
]
SHIPMENT_COLS = ["shipment_id", "supplier_id", "product_id", "quantity", "eta_date", "status"]

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TRUE = {"true", "1", "yes", "y"}
_FALSE = {"false", "0", "no", "n"}


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# --------------------------------------------------------------------- scalar parsers


def parse_iso_date(value: Any) -> str | None:
    """Return the value as a strict YYYY-MM-DD string, or None if it isn't a valid date."""
    if not isinstance(value, str) or not _ISO.match(value.strip()):
        return None
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return value.strip()


def parse_int(value: Any) -> int | None:
    """Whole numbers only (30, "30", 30.0). Rejects bools, NaN, fractions, text."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        f = float(str(value).strip())
    except ValueError:
        return None
    return int(f) if f == f and f not in (float("inf"), float("-inf")) and f == int(f) else None


def _number(value: Any) -> float | None:
    try:
        f = float(str(value).strip())
    except ValueError:
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


# --------------------------------------------------------------------- CSV validators


def _prepare(df: pd.DataFrame, required: list[str], name: str) -> tuple[pd.DataFrame, list[str]]:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValidationError([f"{name}: missing required column(s): {', '.join(missing)}"])
    if df.empty:
        raise ValidationError([f"{name}: file has no data rows"])
    out = df[required].copy().astype(str).apply(lambda col: col.str.strip())
    errors: list[str] = []
    for col in required:
        for i in out.index[(out[col] == "") | (out[col].str.lower() == "nan")]:
            errors.append(f"{name} row {i + 2}: '{col}' is missing")
    return out, errors


def _check_ints(out, col, name, errors, minimum):
    vals = []
    for i, v in out[col].items():
        n = parse_int(v) if v else None
        if v and n is None:
            errors.append(f"{name} row {i + 2}: '{col}' must be a whole number, got '{v}'")
        elif n is not None and n < minimum:
            what = "positive" if minimum == 1 else "non-negative"
            errors.append(f"{name} row {i + 2}: '{col}' must be {what}, got {n}")
        vals.append(n)
    out[col] = vals


def _check_dates(out, col, name, errors):
    vals = []
    for i, v in out[col].items():
        d = parse_iso_date(v) if v else None
        if v and d is None:
            errors.append(f"{name} row {i + 2}: '{col}' must be a valid YYYY-MM-DD date, got '{v}'")
        vals.append(d)
    out[col] = vals


def _check_duplicates(out, col, name, errors):
    for v in out[col][out[col].duplicated() & (out[col] != "")].unique():
        errors.append(f"{name}: duplicate {col} '{v}'")


def validate_inventory(df: pd.DataFrame) -> pd.DataFrame:
    out, errors = _prepare(df, INVENTORY_COLS, "inventory")
    _check_ints(out, "on_hand_qty", "inventory", errors, 0)
    _check_dates(out, "as_of_date", "inventory", errors)
    _check_duplicates(out, "product_id", "inventory", errors)
    if errors:
        raise ValidationError(errors)
    return out.reset_index(drop=True)


def validate_orders(df: pd.DataFrame) -> pd.DataFrame:
    out, errors = _prepare(df, ORDER_COLS, "orders")
    _check_ints(out, "quantity", "orders", errors, 1)
    _check_dates(out, "due_date", "orders", errors)
    _check_duplicates(out, "order_id", "orders", errors)
    flags, pens = [], []
    for i, row in out.iterrows():
        v = row["contractual_priority"].lower()
        if v in _TRUE:
            flags.append(True)
        elif v in _FALSE:
            flags.append(False)
        else:
            if row["contractual_priority"]:
                errors.append(
                    f"orders row {i + 2}: 'contractual_priority' must be true or false, "
                    f"got '{row['contractual_priority']}'"
                )
            flags.append(False)
        p = _number(row["penalty_per_unit"]) if row["penalty_per_unit"] else None
        if row["penalty_per_unit"] and p is None:
            errors.append(f"orders row {i + 2}: 'penalty_per_unit' must be a number, got '{row['penalty_per_unit']}'")
        elif p is not None and p < 0:
            errors.append(f"orders row {i + 2}: 'penalty_per_unit' must be non-negative, got {p:g}")
        pens.append(p)
    out["contractual_priority"] = flags
    out["penalty_per_unit"] = pens
    if errors:
        raise ValidationError(errors)
    return out.reset_index(drop=True)


def validate_shipments(df: pd.DataFrame) -> pd.DataFrame:
    out, errors = _prepare(df, SHIPMENT_COLS, "shipments")
    _check_ints(out, "quantity", "shipments", errors, 1)
    _check_dates(out, "eta_date", "shipments", errors)
    for v in out["shipment_id"][out.duplicated(keep="first")].unique():
        errors.append(f"shipments: duplicate row for shipment '{v}' (would double-count supply)")
    for sid, grp in out.groupby("shipment_id"):
        for col in ("product_id", "supplier_id"):
            if grp[col].nunique() > 1:
                errors.append(f"shipments: shipment '{sid}' has more than one {col}")
    if errors:
        raise ValidationError(errors)
    return out.reset_index(drop=True)


def cross_check(inventory: pd.DataFrame, orders: pd.DataFrame, shipments: pd.DataFrame) -> list[str]:
    """Non-fatal warnings about how the three tables fit together."""
    warnings = []
    known = set(inventory["product_id"])
    for p in sorted(set(orders["product_id"]) - known):
        warnings.append(f"Orders reference product '{p}', which has no inventory row (treated as 0 on hand).")
    for p in sorted(set(shipments["product_id"]) - known):
        warnings.append(f"Shipments reference product '{p}', which has no inventory row.")
    return warnings


# --------------------------------------------------------------------- supplier update


@dataclass
class Batch:
    quantity: Any
    eta_date: Any


@dataclass
class ShipmentUpdate:
    """A proposed schedule change. Holds raw values so invalid input can be shown and corrected."""

    shipment_id: str = ""
    product_id: str = ""
    new_batches: list[Batch] = field(default_factory=list)
    previous_eta_date: str | None = None
    change_type: str = ""
    source_quote: str = ""
    confidence: float | None = None
    missing_fields: list[str] = field(default_factory=list)
    needs_clarification: bool = False


@dataclass
class UpdateCheck:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_update(
    update: ShipmentUpdate, shipments: pd.DataFrame, planning_date: str | None = None
) -> UpdateCheck:
    check = UpdateCheck()
    err, warn = check.errors, check.warnings

    sid = (update.shipment_id or "").strip()
    pid = (update.product_id or "").strip()
    if not sid:
        err.append("Shipment ID is required.")
    if not pid:
        err.append("Product ID is required.")
    if not update.new_batches:
        err.append("At least one delivery batch is required.")

    current = shipments[shipments["shipment_id"] == sid] if sid else shipments.iloc[0:0]
    if sid and current.empty:
        err.append(f"Shipment '{sid}' does not exist in the shipment data; it cannot be updated.")
    elif sid and pid and pid not in set(current["product_id"]):
        err.append(
            f"Product '{pid}' does not match shipment {sid} (which carries {', '.join(sorted(set(current['product_id'])))})."
        )

    total, batches_ok = 0, bool(update.new_batches)
    for n, b in enumerate(update.new_batches, start=1):
        qty = parse_int(b.quantity)
        if qty is None or qty <= 0:
            err.append(f"Batch {n}: quantity must be a positive whole number, got '{b.quantity}'.")
            batches_ok = False
        else:
            total += qty
        d = parse_iso_date(b.eta_date)
        if d is None:
            err.append(f"Batch {n}: '{b.eta_date}' is not a valid YYYY-MM-DD date.")
        elif planning_date and d < planning_date:
            warn.append(f"Batch {n}: date {d} is before the planning date {planning_date}.")

    if not current.empty:
        scheduled = int(current["quantity"].sum())
        if batches_ok and total != scheduled:
            err.append(
                f"Batch quantities sum to {total}, but shipment {sid} is scheduled for {scheduled} units. "
                f"The update must redistribute exactly the scheduled quantity."
            )
        etas = sorted(set(current["eta_date"]))
        prev = (update.previous_eta_date or "").strip()
        if prev and prev not in etas:
            warn.append(
                f"The message says the previous ETA was {prev}, but the current schedule for {sid} "
                f"has {', '.join(etas)}."
            )
        statuses = {s.lower() for s in current["status"]}
        if statuses - {"planned"}:
            warn.append(
                f"Shipment {sid} has status '{', '.join(sorted(statuses))}' (not just 'planned'); "
                f"this update overrides existing confirmed supply information."
            )

    if update.missing_fields:
        warn.append(f"The extraction reported missing fields: {', '.join(update.missing_fields)}.")
    if update.needs_clarification:
        warn.append("The extraction flagged that the supplier message needs clarification.")
    return check


def apply_shipment_update(
    shipments: pd.DataFrame, update: ShipmentUpdate, planning_date: str | None = None
) -> pd.DataFrame:
    """Return a new schedule where the shipment's rows are *replaced* by the new batches.

    Applying the same update twice yields the same table (no double-counting).
    """
    check = validate_update(update, shipments, planning_date)
    if not check.ok:
        raise ValidationError(check.errors)
    sid = update.shipment_id.strip()
    old = shipments[shipments["shipment_id"] == sid].iloc[0]
    new_rows = [
        {
            "shipment_id": sid,
            "supplier_id": old["supplier_id"],
            "product_id": old["product_id"],
            "quantity": parse_int(b.quantity),
            "eta_date": parse_iso_date(b.eta_date),
            "status": old["status"],
        }
        for b in sorted(update.new_batches, key=lambda b: parse_iso_date(b.eta_date))
    ]
    rows, inserted = [], False
    for r in shipments.to_dict("records"):
        if r["shipment_id"] != sid:
            rows.append(r)
        elif not inserted:
            rows.extend(new_rows)
            inserted = True
    return pd.DataFrame(rows, columns=SHIPMENT_COLS)
