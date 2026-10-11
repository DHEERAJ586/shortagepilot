"""Shared session state, dataset loading and plan computation for all screens."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_parser import load_config
from planner import CONTRACT_FIRST, PENALTY_FIRST, PlanResult, build_plan
from validation import (
    ShipmentUpdate, ValidationError, validate_inventory, validate_orders, validate_shipments,
)

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_LABEL = "synthetic sample data"
INACTIVE = {"cancelled", "received"}

# Filled in by app.py so screens can link to each other.
PAGES: dict = {}


@dataclass
class Ctx:
    inventory: pd.DataFrame
    orders: pd.DataFrame
    base_ships: pd.DataFrame
    cur_ships: pd.DataFrame
    label: str
    planning_date: str
    has_update: bool
    plans: dict  # (scenario, policy) -> PlanResult

    def pair(self, policy: str) -> tuple[PlanResult, PlanResult, PlanResult]:
        """(baseline, revised, revised under the other policy) for ``policy``."""
        other = PENALTY_FIRST if policy == CONTRACT_FIRST else CONTRACT_FIRST
        return self.plans[("baseline", policy)], self.plans[("revised", policy)], self.plans[("revised", other)]


# ----------------------------------------------------------------------------- loading


def read_csv(source) -> pd.DataFrame:
    return pd.read_csv(source, dtype=str, keep_default_na=False)


def sample_tables():
    return (
        validate_inventory(read_csv(DATA_DIR / "inventory.csv")),
        validate_orders(read_csv(DATA_DIR / "orders.csv")),
        validate_shipments(read_csv(DATA_DIR / "inbound_shipments.csv")),
    )


def init_state():
    defaults = {
        "dataset": None, "dataset_key": None, "source_mode": "Sample data",
        "revised_ships": None, "draft": None, "draft_source": "", "draft_message": "",
        "draft_id": 0, "parse_cache": {}, "parse_count": 0, "parse_error": "", "notice": "",
        "policy": CONTRACT_FIRST,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    if st.session_state.dataset is None:
        st.session_state.dataset = (*sample_tables(), SAMPLE_LABEL)


def use_sample_dataset():
    st.session_state.dataset = (*sample_tables(), SAMPLE_LABEL)


def context() -> Ctx:
    inv, orders, base, label = st.session_state.dataset
    key = hashlib.sha256("".join(df.to_csv(index=False) for df in (inv, orders, base)).encode()).hexdigest()
    if st.session_state.dataset_key != key:  # new data: drop any update built on the old data
        st.session_state.dataset_key = key
        st.session_state.revised_ships = None
        clear_draft()
    revised = st.session_state.revised_ships
    cur = revised if revised is not None else base
    planning_date = max(inv["as_of_date"])
    plans = {}
    for p in (CONTRACT_FIRST, PENALTY_FIRST):
        plans[("baseline", p)] = build_plan(inv, orders, base, p, planning_date)
        plans[("revised", p)] = build_plan(inv, orders, cur, p, planning_date)
    return Ctx(inv, orders, base, cur, label, planning_date, revised is not None, plans)


# ----------------------------------------------------------------------------- draft & policy


def set_draft(update: ShipmentUpdate, source: str, message: str):
    st.session_state.update(
        draft=update, draft_source=source, draft_message=message,
        draft_id=st.session_state.draft_id + 1, parse_error="", notice="",
    )


def clear_draft():
    st.session_state.update(draft=None, draft_source="", draft_message="", parse_error="")


def config() -> dict:
    return load_config()
