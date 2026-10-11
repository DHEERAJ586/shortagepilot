"""Presentation helpers shared by the screens: styling, tables, the delivery grid."""

import html
from datetime import datetime
from functools import lru_cache

import pandas as pd
import streamlit as st

from planner import (
    AT_RISK, CONTRACT_FIRST, LATE, ON_TIME, PARTIALLY_LATE, PENALTY_FIRST, POLICY_LABELS, UNFULFILLED,
)
import art
import state

STATUS_ICON = {ON_TIME: "🟢", AT_RISK: "🟡", PARTIALLY_LATE: "🟠", LATE: "🔴", UNFULFILLED: "🔴"}
SEVERITY = {UNFULFILLED: 0, LATE: 1, PARTIALLY_LATE: 2, AT_RISK: 3, ON_TIME: 4}
POLICY_HELP = {
    CONTRACT_FIRST: "Contractual orders first, then earliest due date, then highest per-unit penalty.",
    PENALTY_FIRST: "Highest per-unit penalty first, then earliest due date, then contractual orders.",
}
MONEY_CFG = {
    "₹/unit": st.column_config.NumberColumn(format="₹%.0f"),
    "Known penalty": st.column_config.NumberColumn(format="₹%.0f"),
}

def _ld(light: str, dark: str) -> str:
    """CSS light-dark(): the browser picks the colour from Streamlit's active theme (color-scheme)."""
    return f"light-dark({light},{dark})"


def page_background(tint: str | None = None) -> str:
    """The .stApp background: optional per-screen glow, dot texture, base gradient (both themes)."""
    dots = art.data_uri(art.pattern("#94a3b8", ".14"))
    glow = f"radial-gradient(900px 380px at 88% -4%,{tint},transparent 65%)," if tint else ""
    base = f"linear-gradient(180deg,{_ld('#f7faff', '#0b1220')} 0%,{_ld('#eef3fa', '#0e1a2e')} 100%)"
    return f'.stApp{{background-color:{_ld("#f4f7fb", "#0b1220")};background-image:{glow}url("{dots}"),{base}}}'


@lru_cache(maxsize=1)
def css() -> str:
    """All app styling. One stylesheet serves light and dark: colours use light-dark(), so the
    page follows the theme picked in Streamlit's top-right menu instantly, without a rerun."""
    card = _ld("#ffffff", "#131e33")
    shadow = f"0 2px 12px {_ld('rgba(15,35,70,.08)', 'rgba(0,0,0,.5)')}"
    return f"""<style>
.block-container{{padding-top:1.6rem;max-width:1250px}}
header[data-testid="stHeader"]{{background:transparent}}
/* sidebar: always a deep navy, darker in dark mode */
[data-testid="stSidebar"]{{background:linear-gradient(180deg,{_ld('#0b1f3a', '#060e1c')} 0%,{_ld('#123a6b', '#0b2447')} 100%)}}
[data-testid="stSidebar"] *{{color:#e8f0fb}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]{{border-radius:10px;margin-bottom:2px}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover{{background:rgba(255,255,255,.10)}}
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"]{{background:rgba(90,169,255,.28);box-shadow:inset 3px 0 0 #5aa9ff}}
[data-testid="stSidebar"] hr{{border-color:rgba(255,255,255,.15)}}
/* cards */
[data-testid="stMetric"]{{background:{card};border-radius:16px;box-shadow:{shadow};padding:.9rem 1rem}}
[data-testid="stMetric"]>div{{border:0}}
[data-testid="stExpander"],[data-testid="stDataFrame"],.sp-card{{background:{card};border-radius:14px;box-shadow:{shadow}}}
[data-testid="stAlert"]{{border-radius:14px}}
h2,h3{{letter-spacing:-.01em;color:{_ld('#0b1f3a', '#e6edf7')}}}
/* hero banner */
.sp-hero{{border-radius:22px;padding:1.7rem 2.2rem;margin:.2rem 0 1.4rem;color:#fff;background-size:cover;
  background-position:right center;box-shadow:0 14px 34px rgba(11,31,58,.28);min-height:170px;
  display:flex;flex-direction:column;justify-content:center}}
.sp-hero .sp-title{{color:#fff!important;font-size:2.3rem;font-weight:800;margin:.1rem 0 .35rem;padding:0;line-height:1.15}}
.sp-hero p{{color:rgba(255,255,255,.88);max-width:520px;margin:0;font-size:1.02rem}}
.sp-kicker{{font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.75);font-weight:700}}
{art.scene_css()}
/* chips, grid */
.sp-sub{{font-size:.78rem;font-weight:400;opacity:.7}}
.sp-pill{{display:inline-block;padding:.12rem .65rem;border-radius:999px;font-size:.78rem;font-weight:600;
  border:1px solid rgba(128,128,128,.3)}}
.sp-ok{{background:rgba(46,160,67,.22)}} .sp-warn{{background:rgba(210,153,34,.28)}}
.sp-bad{{background:rgba(248,81,73,.22)}} .sp-idle{{background:rgba(128,128,128,.18)}}
.sp-grid{{border-collapse:separate;border-spacing:5px;width:100%}}
.sp-grid th{{font-size:.82rem;font-weight:600;text-align:center;vertical-align:bottom}}
.sp-grid td.sp-label{{font-weight:600;white-space:nowrap}}
.sp-grid td.sp-cell{{text-align:center;border-radius:10px;padding:.6rem .35rem;font-weight:700;min-width:64px}}
.sp-cell.ok{{background:rgba(46,160,67,.28)}} .sp-cell.late{{background:rgba(248,81,73,.32)}}
.sp-cell.none{{background:rgba(128,128,128,.10);opacity:.55}}
.sp-cell.due{{box-shadow:inset 0 0 0 2px {_ld('rgba(11,31,58,.55)', 'rgba(255,255,255,.75)')}}}
</style><style>{page_background()}</style>"""


def pill(text: str, kind: str = "idle") -> str:
    return f"<span class='sp-pill sp-{kind}'>{html.escape(text)}</span>"


def fmt_date(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.day} {d:%b}"


STEPS = {"overview": 1, "supplier": 2, "decision": 3, "allocation": 4, "orders": 5, "export": 6}


def header(scene: str, title: str, subtitle: str):
    """Illustrated hero banner; each screen has its own scene and page tint."""
    tint = art.PALETTE[scene][1]
    st.markdown(
        f"<style>{page_background(tint)}</style>"
        f"<div class='sp-hero {scene}'><div class='sp-kicker'>Step {STEPS[scene]} of {len(STEPS)}</div>"
        f"<h1 class='sp-title'>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>",
        unsafe_allow_html=True,
    )


def policy_selector(key: str) -> str:
    """Policy radio kept in sync across screens through session_state['policy']."""
    options = [CONTRACT_FIRST, PENALTY_FIRST]

    def sync():
        st.session_state.policy = st.session_state[f"policy_{key}"]

    st.radio(
        "Allocation policy", options, index=options.index(st.session_state.policy),
        format_func=lambda p: POLICY_LABELS[p], horizontal=True, key=f"policy_{key}", on_change=sync,
        help="\n\n".join(f"**{POLICY_LABELS[p]}:** {h}" for p, h in POLICY_HELP.items()),
    )
    p = st.session_state.policy
    st.caption(
        f"{POLICY_HELP[p]}  \n**Rule-based allocation plan: a transparent priority heuristic, "
        f"not a globally optimal solution.**"
    )
    return p


# ----------------------------------------------------------------------------- tables


def allocation_schedule(plan) -> pd.DataFrame:
    """Date-by-date table: supply landing that day and who gets it (late units labelled)."""
    supply = plan.supply.groupby("date")["quantity"].sum()
    customers = list(dict.fromkeys(plan.orders["customer_name"]))
    rows = []
    for d, units in supply.items():
        day = plan.allocations[plan.allocations["date"] == d]
        row = {"Date": d, "Supply available": int(units)}
        for c in customers:
            m = day[day["customer_name"] == c]
            on_time = int(m.loc[m["timing"] == "On time", "quantity"].sum())
            late = int(m.loc[m["timing"] == "Late", "quantity"].sum())
            parts = ([str(on_time)] if on_time else []) + ([f"{late} late"] if late else [])
            row[c] = " + ".join(parts) or "—"
        rows.append(row)
    return pd.DataFrame(rows)


def delivery_grid(plan) -> str:
    """HTML grid: one row per order, one column per supply date, coloured by on-time / late."""
    supply = plan.supply.groupby("date")["quantity"].sum()
    dates = list(supply.index)
    head = "".join(
        f"<th>{fmt_date(d)}<div class='sp-sub'>+{int(supply[d])} units</div></th>" for d in dates
    )
    rows = []
    for o in plan.orders.itertuples():
        mine = plan.allocations[plan.allocations["order_id"] == o.order_id]
        tags = f"due {fmt_date(o.due_date)} · {o.quantity} units" + (" · contractual" if o.contractual else "")
        cells = []
        for d in dates:
            m = mine[mine["date"] == d]
            due = " due" if d == o.due_date else ""
            if m.empty:
                cells.append(f"<td class='sp-cell none{due}'>·</td>")
            else:
                late = (m["timing"] == "Late").any()
                label = f"{int(m['quantity'].sum())}" + (" late" if late else "")
                cells.append(f"<td class='sp-cell {'late' if late else 'ok'}{due}'>{label}</td>")
        if o.unfulfilled_qty:
            cells.append(f"<td class='sp-cell late'>{o.unfulfilled_qty} short</td>")
        else:
            cells.append("<td class='sp-cell none'>·</td>")
        rows.append(
            f"<tr><td class='sp-label'>{html.escape(o.customer_name)}"
            f"<div class='sp-sub'>{html.escape(tags)}</div></td>{''.join(cells)}</tr>"
        )
    return (
        f"<table class='sp-grid'><tr><th></th>{head}<th>Undelivered</th></tr>{''.join(rows)}</table>"
        "<div class='sp-sub'>Green = delivered on time · Red = delivered late or never · "
        "Outlined cell = the order's due date.</div>"
    )


def order_table(plan, baseline) -> pd.DataFrame:
    o = plan.orders.copy()
    o["Baseline status"] = o["order_id"].map(baseline.orders.set_index("order_id")["status"]).map(
        lambda s: f"{STATUS_ICON[s]} {s}"
    )
    o["Status"] = o["status"].map(lambda s: f"{STATUS_ICON[s]} {s}")
    o["rank"] = o["status"].map(SEVERITY)
    o = o.sort_values(["rank", "order_id"])
    out = o[[
        "order_id", "customer_name", "contractual", "due_date", "quantity", "on_time_qty",
        "late_delivered_qty", "unfulfilled_qty", "penalty_per_unit", "penalty", "Status", "Baseline status",
    ]]
    return out.rename(columns={
        "order_id": "Order", "customer_name": "Customer", "contractual": "Contractual",
        "due_date": "Due", "quantity": "Ordered", "on_time_qty": "On time",
        "late_delivered_qty": "Delivered late", "unfulfilled_qty": "Undelivered",
        "penalty_per_unit": "₹/unit", "penalty": "Known penalty",
    })


def policy_summary(ctx: state.Ctx) -> pd.DataFrame:
    rows = []
    for policy in (CONTRACT_FIRST, PENALTY_FIRST):
        for scenario in ("Baseline", "Revised") if ctx.has_update else ("Baseline",):
            t = ctx.plans[(scenario.lower(), policy)].totals
            rows.append({
                "Policy": POLICY_LABELS[policy], "Schedule": scenario,
                "Late units": t["late_qty"], "Known penalty": t["penalty"],
                "Contractual orders late": t["contractual_at_risk"],
                "Contractual units late": t["contractual_units_late"],
                "Undelivered": t["unfulfilled_qty"],
            })
    return pd.DataFrame(rows)


def next_step(page_key: str, label: str):
    st.page_link(state.PAGES[page_key], label=label)
