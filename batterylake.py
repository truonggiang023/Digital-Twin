"""Read-only integration with BatteryLake's public metadata JSON interface."""
import json
import re
import threading
import urllib.request

UPSTREAM_REF = '8d2a7304e4841b815287d3d0b2fcc67fea95b200'
BASE_URL = f'https://raw.githubusercontent.com/tianwen1209/batterylake/{UPSTREAM_REF}/metadata/'


class BatteryLakeError(Exception):
    pass


class BatteryLake:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    def read(self, path):
        with self.lock:
            if path in self.cache:
                return self.cache[path]
            try:
                request = urllib.request.Request(BASE_URL + path, headers={'User-Agent':'Digital-Twin/1.0'})
                with urllib.request.urlopen(request, timeout=15) as response:
                    body = response.read(8*1024*1024+1)
                if len(body) > 8*1024*1024:
                    raise ValueError('Metadata response too large')
                value = json.loads(body)
                if not isinstance(value, dict) or value.get('schema_version') != '2.0.0':
                    raise ValueError('Unsupported metadata schema')
            except (OSError, ValueError) as error:
                raise BatteryLakeError('Cannot read BatteryLake metadata; check Internet access to raw.githubusercontent.com') from error
            self.cache[path] = value
            return value

    def provenance(self, path):
        return dict(source='batterylake-public-metadata', upstream_repository='tianwen1209/batterylake',
                    upstream_commit=UPSTREAM_REF, url=BASE_URL+path,
                    measurement_data_loaded=False, prediction_api_connected=False)

    def catalog(self, chemistry='', task='', search=''):
        index = self.read('index.json')
        rows = index.get('datasets')
        if not isinstance(rows, list) or any(not isinstance(r,dict) for r in rows):
            raise BatteryLakeError('Invalid BatteryLake catalog')
        items = [row for row in rows
                 if (not chemistry or chemistry in row.get('cathode_chemistries', []))
                 and (not task or task in row.get('supported_tasks', []))
                 and (not search or search.casefold() in
                      ' '.join(str(row.get(k,'')) for k in ['dataset_name','ref_name','institution']).casefold())]
        return dict(items=items, total=len(rows), matched=len(items), facets=index.get('facets',{}),
                    generated=index.get('generated'), **self.provenance('index.json'))

    def dataset(self, dataset_id):
        if not re.fullmatch(r'dataset_[0-9]{2}', dataset_id):
            raise ValueError('Invalid dataset ID')
        if dataset_id not in {r['dataset_id'] for r in self.catalog()['items']}:
            raise ValueError('Dataset not found')
        path=f'datasets/{dataset_id}.json'
        record=self.read(path)
        if record.get('dataset_id') != dataset_id:
            raise BatteryLakeError('Dataset identity mismatch')
        return dict(record=record, **self.provenance(path))
