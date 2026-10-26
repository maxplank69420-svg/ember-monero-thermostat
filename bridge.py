#!/usr/bin/env python3
"""Ember local sensor/XMRig bridge. Python standard library only."""
import json
import math
import os
import signal
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent / 'dist'
PORT = int(os.environ.get('EMBER_PORT', '8787'))
SENSOR = os.environ.get('EMBER_SENSOR_URL', '')
MINER = os.environ.get('EMBER_XMRIG_URL', 'http://127.0.0.1:18088').rstrip('/')
TOKEN = os.environ.get('EMBER_XMRIG_TOKEN', '')


def request_json(url, body=None, token=None):
    headers = {'Accept': 'application/json', 'Cache-Control': 'no-cache'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


def validate_control(data):
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    out = {}
    for key, low, high in [('target', 16, 30), ('manual', 10, 100)]:
        if key in data:
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key} must be between {low} and {high}')
            out[key] = value
    if 'mode' in data:
        if data['mode'] not in ('auto', 'manual', 'off'):
            raise ValueError('Invalid thermostat mode')
        out['mode'] = data['mode']
    if 'paused' in data:
        if type(data['paused']) is not bool:
            raise ValueError('paused must be a boolean')
        out['paused'] = data['paused']
    return out


def compute_duty(target, current, mode, manual, paused, calling):
    if paused or mode == 'off' or current >= 30:
        return 0, False
    if mode == 'manual':
        return manual, False
    if current >= target + .3:
        calling = False
    elif current <= target - .3:
        calling = True
    return (max(15, min(100, (target - current) * 40)) if calling else 0), calling


class Controller:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = dict(kind='ember-bridge', target=23, mode='off', manual=65,
                          paused=False, current=0, duty=0, hashrate=0,
                          heating=False, error='Waiting for sensor')
        self.last_client = 0
        self.last_run = None
        self.calling = False
        self.closed = threading.Event()

    def command(self, running):
        # Reassert even unchanged commands: external miner state may have changed.
        result = request_json(MINER + '/json_rpc',
                              {'jsonrpc': '2.0', 'id': 1, 'method': 'resume' if running else 'pause'}, TOKEN)
        if result.get('error'):
            raise RuntimeError('XMRig rejected control command')
        if 'result' not in result:
            raise RuntimeError('Invalid XMRig response')
        self.last_run = running

    def snapshot(self, heartbeat=False):
        with self.lock:
            if heartbeat:
                self.last_client = time.monotonic()
            return self.state.copy()

    def control(self, data):
        data = validate_control(data)
        with self.lock:
            self.state.update(data)
            self.last_client = time.monotonic()
            # Off and pause take effect before this request returns.
            if self.state['mode'] == 'off' or self.state['paused']:
                try:
                    self.command(False)
                    self.state.update(heating=False, duty=0, hashrate=0)
                except Exception:
                    self.state.update(error='Cannot reach XMRig to pause it', heating=False, duty=0, hashrate=0)
            return self.state.copy()

    def tick(self):
        with self.lock:
            try:
                if not SENSOR or not TOKEN:
                    raise RuntimeError('Configure sensor URL and XMRig API token')
                data = request_json(SENSOR)
                current = data.get('temperature')
                if isinstance(current, bool) or not isinstance(current, (int, float)) or not math.isfinite(current) or not -10 <= current <= 60:
                    raise RuntimeError('Invalid sensor temperature')
                # Optional Unix timestamp allows the sensor to report stale data.
                if 'timestamp' in data and (not isinstance(data['timestamp'], (int, float)) or not math.isfinite(data['timestamp']) or abs(time.time() - data['timestamp']) > 30):
                    raise RuntimeError('Sensor reading is stale')
                self.state['current'] = current
                if time.monotonic() - self.last_client > 30:
                    self.state['paused'] = True
                duty, self.calling = compute_duty(self.state['target'], current, self.state['mode'], self.state['manual'], self.state['paused'], self.calling)
                running = duty > 0 and (time.monotonic() % 60) < 60 * duty / 100
                self.command(running)
                summary = request_json(MINER + '/2/summary', token=TOKEN)
                rate = ((summary.get('hashrate') or {}).get('total') or [0])[0] or 0
                self.state.update(duty=round(duty), heating=running, hashrate=rate if running else 0,
                                  error='Room safety limit reached (30°C)' if current >= 30 else None)
            except Exception as error:
                # Never resume on a failed or invalid sensor/telemetry read.
                message = str(error) if isinstance(error, RuntimeError) else 'Sensor or miner connection failed'
                try:
                    self.command(False)
                except Exception:
                    message += '; XMRig pause unconfirmed — check the miner'
                self.state.update(error=message, heating=False, duty=0, hashrate=0)

    def run(self):
        while not self.closed.is_set():
            self.tick()
            self.closed.wait(2)

    def stop(self):
        self.closed.set()
        with self.lock:
            try:
                self.command(False)
            except Exception:
                print('Could not confirm XMRig pause. Check your miner directly.', flush=True)


class Handler(SimpleHTTPRequestHandler):
    controller = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def allowed(self):
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
        if host not in allowed:
            return False
        origin = self.headers.get('Origin')
        return origin is None or origin in {f'http://{h}' for h in allowed}

    def respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return self.respond(403, {'error': 'Local access only'})
        if self.path == '/api/status':
            return self.respond(200, self.controller.snapshot(heartbeat=True))
        if self.path.startswith('/api/'):
            return self.respond(404, {'error': 'Unknown endpoint'})
        return super().do_GET()

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {'error': 'Local origin required'})
        if self.path != '/api/control':
            return self.respond(404, {'error': 'Unknown endpoint'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.respond(415, {'error': 'Expected application/json'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2048:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            self.respond(200, self.controller.control(data))
        except (ValueError, TypeError):
            self.respond(400, {'error': 'Invalid controls: target 16–30, manual 10–100, mode auto/manual/off, paused boolean'})


if __name__ == '__main__':
    for address in (SENSOR, MINER):
        if address and urlsplit(address).scheme not in ('http', 'https'):
            raise SystemExit('Sensor and miner URLs must use http or https')
    controller = Controller()
    Handler.controller = controller
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    threading.Thread(target=controller.run, daemon=True).start()
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    print(f'Ember local thermostat: http://127.0.0.1:{PORT}', flush=True)
    print('Starts OFF. Configure your sensor and XMRig, then select Auto in the app.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        server.server_close()
