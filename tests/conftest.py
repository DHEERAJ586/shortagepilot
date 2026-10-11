from pathlib import Path

import pandas as pd
import pytest

from validation import (
    Batch, ShipmentUpdate, validate_inventory, validate_orders, validate_shipments,
)

DATA = Path(__file__).resolve().parent.parent / "data"
PLANNING_DATE = "2026-10-11"


def read(name):
    return pd.read_csv(DATA / name, dtype=str, keep_default_na=False)


@pytest.fixture
def inventory():
    return validate_inventory(read("inventory.csv"))


@pytest.fixture
def orders():
    return validate_orders(read("orders.csv"))


@pytest.fixture
def shipments():
    return validate_shipments(read("inbound_shipments.csv"))


@pytest.fixture
def planning_date():
    return PLANNING_DATE


@pytest.fixture
def sample_update():
    return ShipmentUpdate(
        shipment_id="SH-77",
        product_id="CAP-001",
        previous_eta_date="2026-10-12",
        new_batches=[Batch(30, "2026-10-13"), Batch(20, "2026-10-15")],
    )
