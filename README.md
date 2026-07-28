# Real-Time Retail Analytics Pipeline

A local, end-to-end streaming data pipeline that simulates a live e-commerce store, processes order activity in real time with **PySpark Structured Streaming**, and surfaces the results — including an **LLM-generated business summary** — on an auto-refreshing **Streamlit** dashboard.

Built as a portfolio project combining data engineering (streaming ingestion, schema design, windowed aggregation) with a GenAI layer on top, using a real e-commerce REST API rather than a static dataset.

## What it looks like

*(Add a screenshot or short screen-recording of the dashboard here.)*

## Architecture

Five independent processes run continuously, each doing one job and handing off to the next:

```
Synthetic Data Generator          Order Poller                 Spark Structured Streaming
  (creates fake orders)    -->   (pulls new orders    -->        (reads JSON files,
   via WooCommerce REST          via REST API, lands            computes running totals
   API, POST)                    as JSON files)                 + hourly trend, writes
                                                                  small "scoreboard" files)
                                                                          |
                                                                          v
                                                                  AI Summary Writer
                                                                  (reads scoreboard,
                                                                   asks Groq/Llama for a
                                                                   plain-English summary
                                                                   every 90s)
                                                                          |
                                                                          v
                                                                  Streamlit Dashboard
                                                                  (reads all scoreboard
                                                                   files, auto-refreshes
                                                                   every 5s)
```

Nothing in this chain talks directly to more than one neighbor — the dashboard never touches Spark or WooCommerce, Spark never touches WooCommerce directly either. Each stage reads/writes plain files, which keeps every piece independently testable and replaceable.

## Components

| File | Role |
|---|---|
| `synthetic_data_generator_6.ipynb` | Generates realistic products, customers, and orders (with Indian addresses via Faker) and pushes them into a live WooCommerce store through its REST API, so the store behaves as if it has real traffic. Also simulates order status transitions (`pending` → `processing` → `completed`). |
| `order_poller.ipynb` | Polls the WooCommerce REST API (`modified_after` filter) for new or updated orders and lands each one as a JSON snapshot file in `woo_orders_landing/`. |
| `live_scoreboard_writer_1.ipynb` | Reads the landing folder with **PySpark Structured Streaming**, computes revenue by product, revenue by state, order status breakdown, average fulfillment time, and an hourly revenue trend — and writes the results to small JSON "scoreboard" files. |
| `ai_summary_writer.ipynb` | Reads the scoreboard, builds a compact prompt from the current numbers, and asks **Groq** (`llama-3.3-70b-versatile`) to write a short plain-English business summary every 90 seconds. |
| `dashboard_app.py` | A **Streamlit** app that reads the scoreboard files (including the AI summary) and displays KPIs, charts, and tables, auto-refreshing every 5 seconds via `st.fragment(run_every="5s")`. |

## Tech stack

Python · WooCommerce REST API · PySpark (Structured Streaming) · Groq (Llama 3.3 70B) · Streamlit · Altair · Plotly · pandas · Faker · python-dotenv

## Setup

### Prerequisites
- Python 3.11, Java (required by PySpark)
- A local WordPress + WooCommerce site (this project was built against [LocalWP](https://localwp.com/), with SSL enabled — WooCommerce's REST API doesn't reliably support Basic Auth over plain HTTP)
- A free [Groq API key](https://console.groq.com)

### Install
```bash
pip install -r requirements.txt
```

### Configure
1. In WooCommerce Admin → Settings → Advanced → REST API, generate a key with **Read/Write** permissions.
2. Copy `.env.example` to `.env` and fill in your real values:
   ```
   WC_URL=https://your-site.local
   WC_CONSUMER_KEY=ck_...
   WC_CONSUMER_SECRET=cs_...
   GROQ_API_KEY=gsk_...
   ```
   `.env` is gitignored — your keys never get committed.

### Run
Start each of these, in order, and leave them all running simultaneously:

1. `synthetic_data_generator_6.ipynb` — run all cells (last cell: `run(n_orders=None)`)
2. `order_poller.ipynb` — run all cells (last cell: `run_poller(n_polls=None)`)
3. `live_scoreboard_writer_1.ipynb` — run all cells (last cell starts the Spark streaming queries)
4. `ai_summary_writer.ipynb` — run all cells (last cell: `run()`)
5. In a terminal: `streamlit run dashboard_app.py`

Open the local URL Streamlit prints (usually `http://localhost:8501`).

## Design decisions

A few choices worth explaining, since they weren't the only options:

- **WooCommerce instead of Twitter/X or a stock-ticker API.** These are the more common choices for a "real-time streaming" portfolio project, but the X API moved to paid-only access, and both options are generic — an e-commerce API is a more distinctive data source and produces a richer, more relatable dataset (products, customers, order lifecycles) than a raw text/price feed.
- **Polling (`modified_after`) instead of webhooks or Kafka.** WooCommerce's REST API is pull-based. Polling is simpler to run locally than standing up Kafka or a webhook receiver, and it's a legitimate real-world integration pattern in its own right — not just a shortcut.
- **Filtering on `modified_after`, not just `after`.** This captures status *changes* (an order moving from `pending` to `completed`), not only newly created orders — so the pipeline reflects the full order lifecycle, not just arrivals.
- **Unwindowed aggregation for small-cardinality dimensions (product, status, state), windowed aggregation for the trend line.** A single running total only ever climbs and can't show whether activity is speeding up or slowing down. Splitting these two — lifetime totals vs. an hourly trend — gives both a headline number and an actual shape to the data.
- **JSON scoreboard files instead of a database.** The scoreboard is small (a handful of KB) and ephemeral by design; a database would only pay for its complexity if the project needed flexible historical queries, which wasn't a goal here. The landing zone (raw JSON per order) follows the same "bronze layer" pattern used in production data pipelines.
- **Groq instead of OpenAI for the LLM layer**, and a 90-second refresh instead of matching the dashboard's 5-second refresh — an LLM call costs money and takes a few seconds, and the underlying numbers don't meaningfully change second to second.

## Known limitations

- **Local-only.** All five processes run on one machine; nothing here is deployed. The WooCommerce store itself only exists via LocalWP, which is a real blocker to cloud deployment — the store would need to move to real hosting before any part of this could run on, say, AWS.
- **No historical query support.** Since the scoreboard only tracks running totals and a rolling set of recent orders, arbitrary historical questions ("what were sales last Tuesday between 2–4pm?") aren't supported without re-deriving them from the raw landing zone.
- **Single-node Spark.** Runs with `local[*]`, not a real cluster — appropriate for this data volume, not representative of production Spark deployment.

## Possible extensions

- Persist the landing zone and scoreboard to Delta Lake instead of plain JSON, for time-travel and ACID guarantees.
- Add a forecasting or customer segmentation model (RFM + clustering) on top of the order history.
- Containerize the full pipeline with Docker Compose, including a scripted (WP-CLI) WooCommerce setup, for one-command reproducibility.
