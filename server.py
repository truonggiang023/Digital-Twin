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
from batterylake import BatteryLake, BatteryLakeError
from ml_inference import predict as ml_predict
from live_features import EarlyDischargeWindow
from doe import schema as doe_schema, prepare as doe_prepare, run_experiment
from project_store import ProjectStore
import workspace_api


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
        self.alarms = []
        self.safety_stop = False
        self.pending_fault = None
        self.live_windows = [EarlyDischargeWindow() for _ in range(12)]
        self.discharge_starts = [None]*12
        self.previous_stages = ['ready']*12
        self.previous_times = [0.0]*12
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
                                   status='ready', error='', live_ml=self.waiting_prediction(),
                                   live_ml_history=[],live_soh_history=[dict(time_s=0,simulated_soh_percent=100)], **battery.health()))

    @staticmethod
    def waiting_prediction():
        return dict(status='waiting',remaining_cycles=None,soh_percent=None,
                    feature_cycle=None,updated_time_s=None,sample_count=0,
                    window_s=600,experimental=True,valid_for_hardware=False,
                    reason='Waiting for 600 seconds of discharge telemetry')

    def collect_prediction(self,index):
        cell=self.cells[index]
        stage=cell['stage']
        if cell['time_s']-cell['live_soh_history'][-1]['time_s']>=30:
            cell['live_soh_history'].append(dict(time_s=cell['time_s'],simulated_soh_percent=cell['soh_percent']))
            cell['live_soh_history']=cell['live_soh_history'][-2048:]
        if stage=='discharge':
            if self.previous_stages[index]!='discharge':
                self.discharge_starts[index]=self.previous_times[index]
                if cell['live_ml']['feature_cycle']!=cell['cycle']:
                    cell['live_ml']['status']='collecting'
            try:
                features=self.live_windows[index].add(
                    cycle=cell['cycle'],stage=stage,time_s=cell['time_s'],
                    voltage_v=cell['voltage_v'],current_a=cell['current_a'],
                    temperature_c=cell['temperature_c'],
                    ambient_temperature_c=self.batteries[index].ambient_c,
                    stage_start_s=self.discharge_starts[index])
                window=self.live_windows[index]
                cell['live_ml']['sample_count']=window.count
                if features:
                    prediction=ml_predict(features)
                    cell['live_ml']=dict(**prediction,status='ready',experimental=True,
                                         valid_for_hardware=False,feature_cycle=cell['cycle'],
                                         updated_time_s=cell['time_s'],sample_count=window.count,
                                         window_s=600,features=features,
                                         reason='NASA-trained model applied to simulated signals; not calibrated')
                    cell['live_ml_history'].append(dict(cycle=cell['cycle'],time_s=cell['time_s'],
                                                       soh_percent=prediction['soh_percent'],
                                                       simulated_soh_percent=cell['soh_percent'],
                                                       remaining_cycles=prediction['remaining_cycles']))
                    cell['live_ml_history']=cell['live_ml_history'][-200:]
                elif window.error:
                    cell['live_ml'].update(status='insufficient',reason=window.error)
            except (ValueError,OSError) as error:
                cell['live_ml'].update(status='error',reason=str(error))
        elif self.previous_stages[index]=='discharge' and not self.live_windows[index].ready:
            cell['live_ml'].update(status='insufficient',reason='Discharge ended before a complete 600-second window')
        self.previous_stages[index]=stage
        self.previous_times[index]=cell['time_s']

    def tick(self, wall_dt):
        if not self.running:
            return
        self.fraction += min(wall_dt, 0.5) * self.speed
        steps = int(self.fraction)
        self.fraction -= steps
        for _ in range(steps):
            for index, (cell, stream) in enumerate(zip(self.cells, self.streams)):
                if cell['status'] in ('complete', 'fault'):
                    continue
                try:
                    cell.update(next(stream), status='running')
                except StopIteration:
                    cell.update(status='complete', current_a=0)
                except RuntimeError as error:
                    self.trip(cell, str(error))
                    return
                if self.pending_fault and self.pending_fault['cell']==index+1:
                    kind=self.pending_fault['kind']
                    if kind=='overheat':cell['temperature_c']=50
                    elif kind=='overvoltage':cell['voltage_v']=4.5
                    elif kind=='overcurrent':cell['current_a']=8
                    elif kind=='capacity_drop':
                        self.batteries[index].aging_damage+=0.5
                        cell.update(self.batteries[index].health())
                    self.pending_fault=None
                reason=None
                if cell['temperature_c']>=45:reason='Quá nhiệt: ≥45 °C'
                elif cell['voltage_v']>4.2+1e-5 or cell['voltage_v']<3-1e-5:reason='Điện áp ngoài giới hạn 3.0–4.2 V'
                elif abs(cell['current_a'])>2.2:reason='Quá dòng: >2.2 A'
                elif cell['soh_percent']<80:reason='SOH dưới ngưỡng an toàn 80%'
                if reason:
                    self.trip(cell,reason)
                    return
                self.collect_prediction(index)
        if all(c['status'] in ('complete', 'fault') for c in self.cells):
            self.running = False

    def trip(self, cell, reason):
        observed=dict(temperature_c=cell['temperature_c'],voltage_v=cell['voltage_v'],
                      current_a=cell['current_a'],soh_percent=cell['soh_percent'])
        self.alarms.append(dict(cell=cell['id'],time_s=cell['time_s'],reason=reason,observed=observed))
        cell.update(status='fault',error=reason)
        self.running=False
        self.safety_stop=True
        for c in self.cells:
            c['current_a']=0
            if c['status']=='running':c['status']='stopped'
            if c['live_ml']['remaining_cycles'] is not None:
                c['live_ml']['status']='safety_stop'

    def snapshot(self):
        return dict(running=self.running, speed=self.speed, cells=self.cells,
                    temperature_min=20, temperature_max=45,alarms=self.alarms,
                    safety_stop=self.safety_stop,pending_fault=self.pending_fault)


def make_handler(rack,workspace=None):
    lake = BatteryLake()
    store=[workspace]
    store_lock=threading.Lock()
    def workspace_store():
        with store_lock:
            if store[0] is None:store[0]=ProjectStore(Path(__file__).parent/'data/workspace.sqlite3')
        return store[0]
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(Path(__file__).parent / 'web'), **kwargs)

        def end_headers(self):
            self.send_header('Cache-Control','no-store')
            super().end_headers()

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
            if url.path=='/':
                self.path='/workflow.html'
                return super().do_GET()
            if url.path.startswith('/api/workspace/'):
                try:self.send_json(workspace_api.get(workspace_store(),url))
                except ValueError as error:self.send_json({'error':str(error)},400)
            elif url.path == '/api/state':
                with rack.lock:
                    self.send_json(rack.snapshot())
            elif url.path=='/api/doe/schema':
                self.send_json(doe_schema())
            elif url.path=='/api/ml/replay':
                try:
                    self.send_json(json.loads((Path(__file__).parent/'results/ml-results.json').read_text(encoding='utf-8')))
                except (OSError,ValueError):
                    self.send_json({'error':'Train the NASA models first with train_ml.py'},503)
            elif url.path.startswith('/api/batterylake/'):
                try:
                    query = parse_qs(url.query, keep_blank_values=True)
                    if url.path == '/api/batterylake/datasets':
                        if set(query) - {'chemistry','task','search'} or any(len(v)!=1 for v in query.values()):
                            raise ValueError('Unknown or duplicate catalog parameter')
                        result = lake.catalog(**{k:v[0] for k,v in query.items()})
                    elif url.path.startswith('/api/batterylake/datasets/') and not query:
                        result = lake.dataset(url.path.rsplit('/',1)[-1])
                    else:
                        self.send_json({'error':'Not found'},404)
                        return
                    self.send_json(result)
                except ValueError as error:
                    self.send_json({'error':str(error)},400)
                except BatteryLakeError as error:
                    self.send_json({'error':str(error)},502)
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
            if self.path not in ('/api/control','/api/ml/predict','/api/doe/plan','/api/doe/run') and not self.path.startswith('/api/workspace/'):
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
                if not 0 < size <= (65536 if self.path.startswith(('/api/doe/','/api/workspace/')) else 1024):
                    raise ValueError('Invalid request length')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('Expected object')
                if self.path.startswith('/api/workspace/'):
                    self.send_json(workspace_api.post(workspace_store(),self.path,data))
                    return
                if self.path.startswith('/api/doe/'):
                    self.send_json(doe_prepare(data)[1] if self.path.endswith('/plan') else run_experiment(data))
                    return
                if self.path=='/api/ml/predict':
                    try:
                        self.send_json(ml_predict(data.get('features')))
                    except OSError:
                        self.send_json({'error':'Train model first with train_ml.py'},503)
                    return
                action = data.get('action')
                if action not in ('start', 'pause', 'reset', 'speed', 'fault'):
                    raise ValueError('Unknown action')
                speed = data.get('speed')
                if action == 'speed' and (type(speed) is not int or speed not in (1, 10, 60, 300)):
                    raise ValueError('Speed must be 1, 10, 60 or 300')
                with rack.lock:
                    if action=='start' and rack.safety_stop:
                        self.send_json({'error':'Safety stop latched; Reset required'},409)
                        return
                    if action == 'reset':
                        rack.reset()
                    elif action=='fault':
                        cell=data.get('cell')
                        kind=data.get('kind')
                        if type(cell) is not int or not 1<=cell<=12 or kind not in ('overheat','overvoltage','overcurrent','capacity_drop'):
                            raise ValueError('Invalid fault scenario')
                        if rack.safety_stop or all(c['status']=='complete' for c in rack.cells):
                            self.send_json({'error':'Reset before injecting a new fault'},409)
                            return
                        if rack.cells[cell-1]['status']=='complete':
                            self.send_json({'error':'Selected cell has completed; Reset first'},409)
                            return
                        rack.pending_fault=dict(cell=cell,kind=kind)
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
