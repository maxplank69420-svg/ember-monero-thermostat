# Ember

**[Open the interactive UI demo](https://ember-monero-thermostat.russet-bull-7151.chatgpt.site)** · [GitHub repository](https://github.com/maxplank69420-svg/ember-monero-thermostat)

The Sites demo is deployed with private access and requires the owner’s ChatGPT sign-in. It uses simulated data and never runs a miner in your browser.

A thermostat-themed Monero heating controller. The hosted app is an interactive demo; real hardware control uses the included local Python bridge. No miner is downloaded, installed, or started by this app.

## Quick start

```bash
git clone https://github.com/maxplank69420-svg/ember-monero-thermostat.git
cd ember-monero-thermostat
python3 -m http.server 8787 --directory dist --bind 127.0.0.1
```

Open **http://127.0.0.1:8787** for the UI demo. Python 3.10+ is sufficient; there are no Python or JavaScript package dependencies. Google Fonts loads optional typefaces; system fonts work offline.

For real hardware control, stop the static preview and follow the bridge setup below.

## Features

- Thermostat dial with a 16–30°C target and Celsius/Fahrenheit display.
- Automatic heating, manual mining duty cycle, Off, and immediate pause/resume.
- Hashrate telemetry, live temperature history, and CSV session event export.
- Local sensor and authenticated XMRig integration; tokens stay on the bridge.
- Temperature cutoff, stale-reading checks, and browser-heartbeat timeout.
- Responsive UI and a hosted demo that requires no hardware.

## Use your room sensor and miner

1. Install and configure [XMRig](https://xmrig.com/) separately with **your** wallet, pool, and chosen CPU thread limit. Follow [XMRig's HTTP API configuration](https://xmrig.com/docs/miner/config/api). Bind its HTTP API to loopback and enable authenticated full access:

   ```json
   "http": {
     "enabled": true,
     "host": "127.0.0.1",
     "port": 18088,
     "access-token": "YOUR_LONG_RANDOM_SECRET",
     "restricted": false
   }
   ```

2. Provide an HTTP sensor endpoint that returns fresh Celsius readings:

   ```json
   {"temperature": 21.4, "timestamp": 1793026800}
   ```

   `timestamp` is an optional Unix timestamp in seconds. When supplied it must be within 30 seconds. The sensor endpoint must produce a fresh measurement on every request, rather than cached data.

3. With Python 3.10 or later, run from this directory:

   ```bash
   export EMBER_SENSOR_URL='http://YOUR_SENSOR/temperature'
   export EMBER_XMRIG_URL='http://127.0.0.1:18088'
   read -rs -p 'XMRig API token: ' EMBER_XMRIG_TOKEN
   export EMBER_XMRIG_TOKEN
   python3 bridge.py
   ```

4. Open **http://127.0.0.1:8787** on the same computer. The real controller starts **Off**, independent of stored demo settings. Select Auto to enable heating. Keep the page open. If a browser reconnects after a timeout, explicitly resume mining.

The bridge connects to an already running miner; it does not launch a miner or manage wallet credentials. Its token stays on the local Python server. The hosted demo cannot access your hardware. Use the local app for live control.

## How control works

- **Auto:** requests heat below target −0.3°C and stops above target +0.3°C. Duty cycle scales with temperature error, up to 100%.
- **Manual:** selects a 10–100% running duty cycle in a 60-second window. This controls running time, not CPU thread intensity.
- **Off / Pause:** sends XMRig's `pause` RPC. Resume uses `resume`. API: [XMRig pause/resume implementation](https://github.com/xmrig/xmrig/issues/479).
- Independent server loop checks the sensor every two seconds (plus network timeouts). Invalid sensor data, failed API reads, a 30°C room limit, or 30 seconds without a browser heartbeat pauses mining. If the miner cannot be contacted, the UI reports that the pause is unconfirmed.
- Shutdown attempts to pause mining. A hard process kill, computer crash, or unreachable XMRig cannot guarantee a pause; use hardware thermal protection and the miner's own protections.

Mining adds heat; it cannot actively cool a room. Choose a target the room and equipment can reach. Set CPU thread/power limits in XMRig and your OS. Duty cycling can interrupt mining work and is intended for room heating, not optimum mining efficiency.

## Interface and data

The demo shows simulated hashrate, heat output, and illustrative temperature history. Live mode uses real XMRig hashrate and sensor readings. It shows no watt estimate without a power meter. Live history is recorded in memory while the page is open; earlier data is not invented. The session log exports to CSV. Unit and demo control preferences persist locally in the browser. No earnings estimates are presented.

## Development

No build step or package dependencies. `python3 bridge.py` serves `dist/` and the local API. For UI-only preview: `python3 -m http.server 8787 --directory dist --bind 127.0.0.1`.

Run controller tests with `python3 -m unittest -v test_bridge.py`. Static files in `dist/` deploy to Sites; `bridge.py` stays on your mining computer.


## Repository layout

```text
.github/workflows/checks.yml  Python controller tests and JS syntax check
.openai/hosting.json          Existing Sites project and static deployment directory
dist/index.html              App markup
dist/style.css               Thermostat theme and responsive layout
dist/app.js                  UI, simulation, history, and local API client
bridge.py                    Loopback-only HTTP server and heating controller
test_bridge.py               Controller and failure-path tests
.env.example                 Documented environment variable template
Makefile                     Preview, bridge, and check shortcuts
CONTRIBUTING.md              Development and validation guide
```

## Checks

```bash
python3 -m unittest -v test_bridge.py
node --check dist/app.js
```

Node.js is only needed for the JavaScript syntax check. GitHub Actions runs both checks on pushes and pull requests. You can also use `make preview`, `make run`, and `make check` on systems with Make installed.

## Local API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/status` | Current temperature, target, mode, duty cycle, hashrate, and errors; refreshes the browser heartbeat. |
| `POST /api/control` | Accepts JSON fields `target` (16–30 Celsius), `mode` (`auto`, `manual`, `off`), `manual` (10–100%), and `paused` (boolean). |

The server binds to loopback, validates Host and Origin headers, and rejects non-JSON control requests. Use it on the same computer as the browser. It is not intended to be exposed directly to the internet.

## Sites demo deployment

The existing Sites project serves `dist/` as a static app, with no build step. `.openai/hosting.json` records its project ID. Hosting runs only the interface; the Python bridge runs on your mining computer. GitHub pushes run checks but do **not** automatically deploy to Sites. Publish updates through the Sites workflow and retain the existing project identity and access settings.

For your own copy, create a new Sites project and replace the project ID with that project's returned ID before publishing. The original project requires its owner's publishing credentials; none are stored in this repository.

## Current limitations

Physical sensor and mining hardware integration has not been exercised on real devices. Controller tests mock the sensor and miner responses. Power output in demo mode is illustrative; live power needs a separate meter. Session history is stored in browser memory and resets on reload. This controller is a prototype and is not a replacement for hardware thermal cutoffs.
