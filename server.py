"""Local realtime dashboard using the same battery model as main.py."""
import argparse
import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from main import Battery, simulate
from aging import forecast


class Rack:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.running = False
        self.speed = 60
        self.fraction = 0.0
        self.cells = []
        self.streams = []
        self.batteries = []
        for i in range(12):
            battery = Battery(capacity_ah=2.5 + 0.025 * i,
                              resistance_ohm=0.07 + 0.004 * i,
                              soc=0.15 + 0.025 * i,
                              temperature_c=25 + 0.2 * i, ambient_c=25 + 0.2 * i)
            self.streams.append(simulate(battery, cycles=3, current_a=2, dt_s=1))
            self.batteries.append(battery)
            self.cells.append(dict(id=i + 1, time_s=0, cycle=1, stage='ready', mode='READY',
                                   voltage_v=battery.ocv, current_a=0, soc=battery.soc,
                                   temperature_c=battery.temperature_c, stage_capacity_ah=0,
                                   status='ready', error='', **battery.health()))

    def tick(self, wall_dt):
        if not self.running:
            return
        self.fraction += min(wall_dt, 0.5) * self.speed
        steps = int(self.fraction)
        self.fraction -= steps
        for _ in range(steps):
            for cell, stream in zip(self.cells, self.streams):
                if cell['status'] in ('complete', 'fault'):
                    continue
                try:
                    cell.update(next(stream), status='running')
                except StopIteration:
                    cell.update(status='complete', current_a=0)
                except RuntimeError as error:
                    cell.update(status='fault', error=str(error), current_a=0)
        if all(c['status'] in ('complete', 'fault') for c in self.cells):
            self.running = False

    def snapshot(self):
        return dict(running=self.running, speed=self.speed, cells=self.cells,
                    temperature_min=20, temperature_max=45)


def make_handler(rack):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(Path(__file__).parent / 'web'), **kwargs)

        def send_json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/state':
                with rack.lock:
                    self.send_json(rack.snapshot())
            elif url.path == '/api/prediction':
                try:
                    query = parse_qs(url.query, keep_blank_values=True)
                    allowed = {'cell', 'temperature_c', 'c_rate', 'dod', 'horizon', 'eol_soh'}
                    if set(query) - allowed or any(len(v) != 1 for v in query.values()):
                        raise ValueError('Unknown or duplicate parameter')
                    cell = int(query.get('cell', ['1'])[0])
                    if not 1 <= cell <= 12:
                        raise ValueError('Cell must be 1 through 12')
                    kwargs = {k: (int(v[0]) if k == 'horizon' else float(v[0]))
                              for k, v in query.items() if k != 'cell'}
                    with rack.lock:
                        b = rack.batteries[cell - 1]
                        result = forecast(b.capacity_ah, b.resistance_ohm, b.soh, b.efc, **kwargs)
                        result.update(cell=cell, source='local-model', time_s=rack.cells[cell-1]['time_s'])
                    self.send_json(result)
                except (ValueError, OverflowError) as error:
                    self.send_json({'error': str(error)}, 400)
            else:
                super().do_GET()

        def do_POST(self):
            if self.path != '/api/control':
                self.send_json({'error': 'Not found'}, 404)
                return
            # Replit terminates HTTPS before forwarding to this HTTP server.
            origin = self.headers.get('Origin')
            host = self.headers.get('Host', '')
            if origin and origin not in ('http://' + host, 'https://' + host):
                self.send_json({'error': 'Origin rejected'}, 403)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024:
                    raise ValueError('Invalid request length')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Expected object')
                action = data.get('action')
                if action not in ('start', 'pause', 'reset', 'speed'):
                    raise ValueError('Unknown action')
                speed = data.get('speed')
                if action == 'speed' and (type(speed) is not int or speed not in (1, 10, 60, 300)):
                    raise ValueError('Speed must be 1, 10, 60 or 300')
                with rack.lock:
                    if action == 'reset':
                        rack.reset()
                    elif action == 'speed':
                        rack.speed = speed
                    else:
                        rack.running = action == 'start'
                    self.send_json(rack.snapshot())
            except (ValueError, TypeError) as error:
                self.send_json({'error': str(error)}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=os.environ.get('PORT', '8000'))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    rack = Rack()
    stop = threading.Event()

    def worker():
        last = time.monotonic()
        while not stop.wait(0.05):
            now = time.monotonic()
            with rack.lock:
                rack.tick(now - last)
            last = now

    server = ThreadingHTTPServer((args.host, args.port), make_handler(rack))
    threading.Thread(target=worker, daemon=True).start()
    print(f'Cycler dashboard listening on port {args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
