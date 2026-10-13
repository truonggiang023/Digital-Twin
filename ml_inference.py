"""Run our exported Random Forest models without pickle or ML dependencies."""
import json
import math
import struct
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def model():
    return json.loads((Path(__file__).parent/'models/nasa-forest.json').read_text())


def predict(features):
    m=model()
    if not isinstance(features,dict) or set(features)!=set(m['features']):
        raise ValueError('Provide exactly the documented early-discharge features')
    values=[]
    for name in m['features']:
        v=features[name]
        if type(v) not in (int,float) or not math.isfinite(v) or not m['bounds'][name][0]<=v<=m['bounds'][name][1]:
            raise ValueError('Feature outside supported range: '+name)
        # sklearn trees route float32 input, including values near split thresholds.
        values.append(struct.unpack('f',struct.pack('f',v))[0])
    def forest(trees):
        outputs=[]
        for t in trees:
            node=0
            while t['left'][node]!=-1:
                node=t['left'][node] if values[t['feature'][node]]<=t['threshold'][node] else t['right'][node]
            outputs.append(t['value'][node])
        return sum(outputs)/len(outputs)
    return dict(source='trained-random-forest', training_cells=m['training_cells'],
                soh_percent=forest(m['soh_trees']),remaining_cycles=max(0,forest(m['rul_trees'])),
                eol_soh_percent=80, model_id=m['model_id'],
                scope='NASA discharge conditions only; not calibrated for arbitrary chemistries')
