# Crust & Co.

Crust & Co. is a console-only LiveKit Agents demo for a fictional pizza
restaurant in Lahore.

## Setup on Windows

The project targets Python 3.13:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
```

Set `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` in `.env` before using LiveKit
Inference.

## Run

Text-only console mode:

```powershell
lk agent console --text src\crustco\main.py
```

Voice console mode:

```powershell
lk agent console --list-devices src\crustco\main.py
lk agent console src\crustco\main.py
```

The `lk agent console` command starts the local single-session console documented
by LiveKit. It does not connect media transport to a LiveKit room.

## Mock data

The demo keeps its seed data in
[`data/seed/mock_data.json`](data/seed/mock_data.json). Edit that file to change the menu,
fixed Lahore branches, customers, orders, or complaints. Delivery addresses are
geocoded and assigned to the nearest active branch. Customer addresses, new
orders, and complaints created during a session are written back to the same file.

## Project structure

```text
src/crustco/
├── main.py
├── config.py
├── agents/              # receptionist, order, order status, complaint
├── orchestration/       # shared state, session setup, and handoffs
├── repositories/        # JSON persistence and domain repositories
└── services/            # external services such as geocoding
data/seed/               # committed JSON seed data
```

The four agents use one shared `AgentSession` and shared Pydantic state while
LiveKit handoffs change which agent handles the conversation.

Milestone 2 adds the receptionist, order, order-status, and complaint agents with
real `AgentSession.update_agent` handoffs and shared Pydantic session state.
Milestone 4 adds JSON-backed menu browsing, modifier validation, and an
in-memory cart. Cart contents are not a committed order until the later order
workflow milestone. Milestone 5 adds phone-based customer lookup, saved delivery
addresses, and order-history lookup for identified callers. Milestone 6 adds order placement with nearest-branch selection and branch
availability validation.
Milestone 7 adds phone-verified order-status lookup and status history.
Milestone 8 adds simple complaint registration linked to a customer and, when
provided, an existing order.
The demo also avoids repeating an identical open complaint and clears the
in-memory cart after a successful order commit.
Milestone 9 hardens the core workflows and verifies the complaint path with
the LiveKit text debugger.
Milestone 10 completes the demo polish with mock-data verification and
end-to-end debugger smoke checks.

The project currently has no automated test suite by design; use the LiveKit
text debugger for quick end-to-end checks.
