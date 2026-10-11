# ShortagePilot

An AI-assisted supply disruption and inventory allocation planner. It turns a supplier's
delivery update into a revised allocation plan and shows which customer orders are at risk.

**Division of labour**

| Layer | Responsibility |
|---|---|
| DeepSeek (one optional API call) | Read an unstructured supplier message and *propose* structured shipment facts as JSON |
| You | Review, correct and explicitly confirm the proposal |
| Python (`validation.py`, `planner.py`) | Validate data, replace the shipment schedule, allocate stock, count late units and penalties |

The LLM never calculates quantities, allocations or money, and never changes the plan on its own.
The explanation text is produced from fixed templates, not a second LLM call.

## The demo scenario

100 units are on hand on 2026-10-11 and 50 more are due on 2026-10-12 (shipment SH-77). Three orders
need 150 units in total (Atlas 60 contractual, Beacon 50 at ₹300/unit late penalty, Crest 40 flexible).
The supplier then splits SH-77: 30 units on 13 Oct and 20 on 15 Oct.

| | Late units | Known penalty | Contractual orders late |
|---|---|---|---|
| Baseline schedule (either policy) | 0 | ₹0 | 0 |
| Revised, Contract-first | 10 (Beacon) | ₹3,000 | 0 |
| Revised, Penalty-first | 10 (Atlas) | ₹0 | 1 (Atlas) |

The two policies trade a financial penalty against a contractual commitment; the app shows both.

## Setup

Requires Python 3.11+ (developed on 3.14).

```bash
cd shortagepilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: add DEEPSEEK_API_KEY to enable AI parsing
streamlit run app.py
```

The app opens at http://localhost:8501. It runs fully **without** an API key: AI parsing is simply
disabled, and you can use *Enter update manually* or *Load offline demo extraction*.

### Environment variables (`.env`, never committed)

| Variable | Default | Meaning |
|---|---|---|
| `DEEPSEEK_API_KEY` | empty | Your DeepSeek key. Without it AI parsing is off |
| `DEEPSEEK_MODEL` | `deepseek-flash` | Model ID, if your account uses another |
| `ENABLE_AI` | `true` | Set `false` to switch AI parsing off even when a key exists |

This key is separate from whatever credentials you use for Claude Code itself.

## Tests

```bash
pytest -q
```

Tests need no API key or network. They cover both policies on baseline and revised schedules,
allocation invariants, input validation, schedule replacement/idempotency, the AI fallback paths
(with a fake client), and an end-to-end UI run.

## Dark mode

Open the ⋮ menu (top right) and choose **Dark**, **Light** or **System**. The whole app, including
banners, cards, tables and charts, switches instantly and keeps your current plan.

## Demo (about two minutes)

Each step is its own screen in the sidebar.

1. **Overview**: point at stock 100, demand 150, incoming 50, net shortage 0 (the stock gap of 50 is covered by inbound), and the baseline outlook with no late units.
2. **Supplier update**: the sample SH-77 message is on the left. Click **Parse supplier update** (or **Load offline demo extraction** if offline). The extracted batches (30 on 13 Oct, 20 on 15 Oct) appear on the right. Edit a date to show validation, fix it, then click **Confirm and apply update**.
3. **Decision comparison**: Contract-first shows 10 late units and ₹3,000, with the supply shift by date. Switch to Penalty-first: ₹0 penalty, but Atlas's contractual commitment is 10 units late. Read "What this means".
4. **Allocation schedule**: the delivery timeline shows who gets what on which date (red = late).
5. **Orders & penalties**: order statuses, contractual risk and the known-penalty summary.
6. **Export**: download the allocation CSV.

## How allocation works

Supply events (stock on hand on the planning date, each inbound batch on its ETA) are processed in
date order. At each event the units go to still-outstanding orders in policy order; partial fulfilment is allowed.

- **Contract-first:** contractual orders, then earliest due date, then highest per-unit penalty, then order ID.
- **Penalty-first:** highest per-unit penalty, then earliest due date, then contractual, then order ID.

This is a transparent rule-based heuristic, **not** a globally optimal solution.

## Assumptions and limitations

- Penalty = (requested − delivered on or before the due date) × per-unit penalty. Late delivery does not erase it. Other penalty contracts are out of scope. Only *known* per-unit penalties are counted; ₹0 means none on file.
- The planning date is the latest `as_of_date` in the inventory file. Shipments with status `cancelled` or `received` add no supply. A shipment ETA before the planning date is treated as arriving on the planning date (noted in the UI).
- Updating a shipment **replaces** all of its rows; batch quantities must sum to the currently scheduled quantity, so total supply cannot change through an update.
- Allocation is by product; there is no lead-time, transport, price, or multi-warehouse logic.
- The "At risk" status is a planner flag: the order is on time only because inbound supply lands exactly on its due date.
- The AI confidence value is an uncalibrated model estimate, shown for information only.
- Supplier text is sent to the DeepSeek API only when you click **Parse supplier update**, together with minimal metadata for shipment IDs named in the message. There is one request per click, no automatic retries, and results are cached per session by message hash.
- Thinking mode is turned off for the extraction request (`extra_body={"thinking": {"type": "disabled"}}`), since extraction needs no reasoning and DeepSeek enables it by default.
- No emails are sent and no external systems are modified. State is in memory; uploads are not stored.

## Layout

```
app.py            Streamlit entry point: navigation, sidebar status
views/            One file per screen: overview, supplier_update, decision,
                  allocation, orders_risk, export
state.py          Session state, dataset loading, plan computation
ui.py             Shared styling, hero banners, tables and the delivery grid
art.py            Inline SVG artwork: one banner scene per screen, page pattern, logo
assets/logo.svg   Sidebar logo
.streamlit/       Light and dark theme palettes
ai_parser.py      DeepSeek extraction, strict JSON parsing, session cache
planner.py        Allocation engine, comparison, template explanations
validation.py     CSV validation, shipment-update validation and replacement
data/             Synthetic sample CSVs
tests/            pytest suite
```
