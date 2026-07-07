# Vega Algorithmic Trading Engine

Event-driven algorithmic trading engine based on WebSocket candle events and REST order execution.

Developed and tested on Bitvavo, while keeping an exchange-agnostic architecture to simplify future integrations.

Independent open-source project focused on runtime reliability, exchange synchronization, recovery mechanisms, operational safety, and disciplined trend-following execution.

---

## Features

- Candle event-driven architecture
- WebSocket market data
- REST order execution
- Live and paper execution modes
- Exchange-authoritative reconciliation
- Runtime crash recovery
- Persistent state management
- Backtesting-ready architecture
- Telegram runtime monitoring
- Risk-based position sizing
- Linux + systemd deployment support

---

## Strategy Overview

The current implementation includes a rule-based trend-following strategy based on:

- EMA cross confirmation
- EMA200 trend filtering
- ATR volatility analysis
- ADX trend strength filtering
- RSI confirmation filters
- Risk-adjusted position sizing

The runtime architecture has been intentionally designed as an independent layer from the trading strategy, allowing future modularization and support for alternative strategies with minimal changes.

This separation also provides a solid foundation for future backtesting, strategy optimization and multi-strategy experimentation without modifying the execution engine.

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
strategy.py
```

### Core Design Principles

- Event-driven execution
- Exchange-authoritative runtime state
- Automatic recovery after unexpected interruptions
- Runtime consistency verification
- Operational monitoring
- Safety-oriented execution flow
- Modular architecture
- Separation between execution engine and trading strategy

---

## Requirements

- Python 3.11+
- Linux (developed and tested on Ubuntu)
- Bitvavo account (for live execution)
- Bitvavo API credentials with appropriate permissions

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

## Disclaimer

This software is provided strictly for educational and research purposes.

Cryptocurrency trading involves substantial financial risk.

The author assumes no responsibility for:

- Financial losses
- Incorrect deployment
- Operational misuse
- Improper configuration
- Unauthorized live trading usage

Use entirely at your own risk.

---

## License

Released under the MIT License.

---

## Author

**Carlo Tronca**

GitHub: https://github.com/carlotronca

Designed and developed as an independent open-source project focused on reliable algorithmic trading system architecture.

Development was supported by ChatGPT (OpenAI) through technical discussions, architectural reviews, and documentation refinement.
