# Vega Algorithmic Trading Engine

Event-driven algorithmic trading framework based on WebSocket candle events and REST order execution.

Developed and tested on Bitvavo while maintaining an exchange-agnostic architecture to simplify future exchange integrations.

Independent open-source project focused on runtime reliability, exchange synchronization, recovery mechanisms, operational safety, and modular strategy execution.

---

## Features

* Event-driven execution engine
* WebSocket market data
* REST order execution
* Live and paper execution modes
* Exchange-authoritative reconciliation
* Runtime crash recovery
* Persistent state management
* Backtesting-ready architecture
* Telegram runtime monitoring
* Risk-based position sizing
* Plugin-based strategy architecture
* Linux + systemd deployment support

---

## Strategy Plugin Architecture

VE243 has been designed as a plugin-based algorithmic trading framework.

The engine is intentionally independent from any trading logic. Every trading strategy is implemented as an independent plugin located under the `strategies/` directory.

Each plugin may consist of one or more Python modules depending on its complexity, while the engine remains responsible only for:

* Market connectivity
* Order execution
* Runtime state management
* Exchange reconciliation
* Recovery mechanisms
* Operational safety
* Monitoring and notifications

This architecture allows new trading strategies to be added without modifying the VE243 Engine.

---

## Included Strategy Plugin

The repository currently includes the **Trend Following Long** strategy plugin.

The plugin implements a rule-based trend-following strategy based on:

* EMA cross confirmation
* EMA200 trend filtering
* ATR volatility analysis
* ADX trend strength filtering
* RSI confirmation filters
* Risk-adjusted position sizing

The current implementation has been primarily designed and tested for the **SOL-USDC** market. Supporting additional trading pairs generally requires only limited configuration changes.

---

## Architecture

```text
engine/
exchange/
execution/
integration_tests/
journal/
live/
market/
models/
notifier/
reconciliation/
recovery/
safety/
secrets/
state/
strategies/
└── trend_following_long/
    └── strategy.py
```

---

## Core Design Principles

* Event-driven execution
* Exchange-authoritative runtime state
* Automatic recovery after unexpected interruptions
* Runtime consistency verification
* Operational monitoring
* Safety-oriented execution flow
* Plugin-based architecture
* Complete separation between execution engine and trading strategies
* Engine-independent strategy development
* Future-ready multi-strategy design

---

## Requirements

* Python 3.11+
* Linux (developed and tested on Ubuntu)
* Bitvavo account (for live execution)
* Bitvavo API credentials with appropriate permissions

---

## Installation

Clone the repository:

```bash
git clone https://github.com/carlotronca/vega-algorithmic-trading-engine.git
cd vega-algorithmic-trading-engine
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

---

## Configuration

Configuration templates are provided with the project.

```text
.env.example
config.example.py
secrets/telegram_bot_token.txt.example
secrets/telegram_chat_id.txt.example
```

Copy and customize the configuration files according to your environment before running the engine.

---

## Running

### Paper Mode

```bash
python live/paper_runtime.py
```

### Live Mode

```bash
python live/live_runtime.py
```

---

## Deployment

The project has been designed, developed and tested on Linux with native **systemd** integration for runtime execution and monitoring services.

---

## Roadmap

The current architecture is designed to support additional independent strategy plugins.

Future plugins currently planned include:

* SR Bounce Plugin
* Trend Following Short Plugin
* Additional strategy plugins

The VE243 Engine is intended to remain stable while trading strategies evolve independently.

---

## Disclaimer

This software is provided strictly for educational and research purposes.

Cryptocurrency trading involves substantial financial risk.

The author assumes no responsibility for:

* Financial losses
* Incorrect deployment
* Operational misuse
* Improper configuration
* Unauthorized live trading usage

Use entirely at your own risk.

---

## License

Released under the MIT License.

---

## Author

**Carlo Tronca**

GitHub: https://github.com/carlotronca

Designed and developed as an independent open-source project focused on reliable algorithmic trading framework architecture.

Development was supported by ChatGPT (OpenAI) through technical discussions, architectural reviews, and documentation refinement.

