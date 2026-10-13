"""Train cross-cell NASA SOH/RUL baselines from measured discharge time series."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

RAW_COMMIT='1e1fc5c5b1a7dd3d44db0df0c429b6e893d4692c'
RAW_URL=f'https://raw.githubusercontent.com/fmardero/battery_aging/{RAW_COMMIT}/discharge.csv'
RAW_SHA='2aad0bb75e77c63439dbe93ddfb91d09e1971b590327c4830fcda0e41440944d'
FEATURES=['cycle','voltage_mean','voltage_std','voltage_end','temperature_mean','current_mean','ambient_temperature']
BOUNDS={'cycle':[1,10000],'voltage_mean':[0,6],'voltage_std':[0,3],'voltage_end':[0,6],
        'temperature_mean':[-20,120],'current_mean':[0,100],'ambient_temperature':[-20,80]}


def extract(path):
    raw=pd.read_csv(path)
    records=[]
    for (cell,cycle),group in raw.groupby(['Battery','id_cycle'],sort=True):
        group=group.sort_values('Time')
        early=group[(group.Time>=0)&(group.Time<=600)]
        capacity=group.Capacity.dropna().unique()
        if len(early)<10 or len(capacity)!=1 or capacity[0]<=0:
            raise ValueError('Invalid raw cycle')
        records.append(dict(cell=cell,cycle=int(cycle),capacity_ah=float(capacity[0]),
                            voltage_mean=float(early.Voltage_measured.mean()),voltage_std=float(early.Voltage_measured.std()),
                            voltage_end=float(early.Voltage_measured.iloc[-1]),temperature_mean=float(early.Temperature_measured.mean()),
                            current_mean=float(early.Current_measured.abs().mean()),ambient_temperature=float(early.ambient_temperature.iloc[0])))
    frame=pd.DataFrame(records)
    for cell,group in frame.groupby('cell'):
        health=100*group.capacity_ah/group.capacity_ah.iloc[0]
        crossing=group.loc[health<=80,'cycle']
        frame.loc[group.index,'soh_percent']=health
        # Never replace a censored EOL with the final recorded cycle.
        frame.loc[group.index,'true_rul']=np.maximum(0,crossing.iloc[0]-group.cycle) if len(crossing) else np.nan
        frame.loc[group.index,'eol_cycle']=crossing.iloc[0] if len(crossing) else np.nan
    return frame


def train(raw_path,output,model_path):
    if not raw_path.exists():
        raw_path.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(RAW_URL,timeout=60) as response:
            body=response.read(40*1024*1024+1)
        if hashlib.sha256(body).hexdigest()!=RAW_SHA:raise ValueError('Raw data checksum mismatch')
        raw_path.write_bytes(body)
    if hashlib.sha256(raw_path.read_bytes()).hexdigest()!=RAW_SHA:raise ValueError('Raw data checksum mismatch')
    frame=extract(raw_path)
    training=['B0005','B0006','B0007'];test_cell='B0018'
    train=frame[frame.cell.isin(training)];test=frame[frame.cell==test_cell]
    if len(train)!=504 or len(test)!=132:raise ValueError('Unexpected source split')
    forests={};metrics={}
    for task,target in [('soh','soh_percent'),('rul','true_rul')]:
        subset=train if task=='soh' else train[(train.true_rul.notna())&(train.cycle<=train.eol_cycle)]
        evaluation=test if task=='soh' else test[(test.true_rul.notna())&(test.cycle<=test.eol_cycle)]
        forest=RandomForestRegressor(n_estimators=80,min_samples_leaf=4,max_depth=9,random_state=42,n_jobs=2)
        forest.fit(subset[FEATURES],subset[target]);forests[task]=forest
        actual=evaluation[target];pred=forest.predict(evaluation[FEATURES])
        metrics[task]=dict(mae=float(mean_absolute_error(actual,pred)),rmse=float(np.sqrt(mean_squared_error(actual,pred))),
                           test_rows=len(evaluation),train_rows=len(subset),
                           constant_baseline_mae=float(mean_absolute_error(actual,np.full(len(actual),subset[target].mean()))),
                           units='percentage points' if task=='soh' else 'cycles')
        frame['predicted_'+task]=forest.predict(frame[FEATURES])
    def export(forest):
        return [dict(left=t.tree_.children_left.tolist(),right=t.tree_.children_right.tolist(),
                     feature=t.tree_.feature.tolist(),threshold=t.tree_.threshold.tolist(),value=t.tree_.value[:,0,0].tolist()) for t in forest.estimators_]
    artifact=dict(model_id='nasa-random-forest-v1',features=FEATURES,bounds=BOUNDS,training_cells=training,
                  soh_trees=export(forests['soh']),rul_trees=export(forests['rul']))
    model_path.parent.mkdir(parents=True,exist_ok=True);model_path.write_text(json.dumps(artifact,separators=(',',':')),encoding='utf-8')
    # Validate dependency-free inference against sklearn on the held-out cell.
    from ml_inference import predict,model
    model.cache_clear()
    for row in test.to_dict('records'):
        prediction=predict({k:row[k] for k in FEATURES})
        # sklearn routes float32 inputs; all observed points must match exported traversal.
        expected_soh=forests['soh'].predict(pd.DataFrame([{k:row[k] for k in FEATURES}]))[0]
        assert abs(prediction['soh_percent']-expected_soh)<1e-7
    replay=[]
    for row in frame[frame.cell==test_cell].to_dict('records'):
        pred=predict({k:row[k] for k in FEATURES})
        replay.append(dict(**{k:row[k] for k in ['cell','cycle','capacity_ah','soh_percent','true_rul','eol_cycle']},
                           features={k:row[k] for k in FEATURES},predicted_soh=pred['soh_percent'],predicted_rul=pred['remaining_cycles']))
    output.mkdir(parents=True,exist_ok=True)
    report=dict(source='NASA measured discharge CSV export',raw_url=RAW_URL,raw_sha256=RAW_SHA,
                batterylake_dataset='dataset_01',training_cells=training,test_cell=test_cell,
                raw_rows=169766,cycle_rows=len(frame),features=FEATURES,early_window_s=600,
                soh_reference='first observed capacity per cell',eol_soh_percent=80,
                split='cross-cell; B0018 never used for fitting',metrics=metrics,replay=replay,
                limitations='Four NASA cells only. No hyperparameter tuning on test data. RUL uses retrospective first observed 80% crossing. Not valid for arbitrary chemistries or synthetic rack cells.')
    (output/'ml-results.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    frame.to_csv(output/'ml-cycle-predictions.csv',index=False,encoding='utf-8')
    (output/'ML-REPORT.md').write_text('\n'.join([
        '# ML prediction on NASA discharge data','',
        f'Source: [{RAW_COMMIT[:7]} CSV export]({RAW_URL}), citing [NASA battery aging](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets). BatteryLake catalog reference: dataset_01.',
        '',f'169,766 time-series rows → {len(frame)} discharge cycles. Train: B0005/B0006/B0007 (504 cycles). Test: B0018 (132 cycles), never used for fitting.',
        '', 'Random Forest: 80 trees, leaf size 4, max depth 9, seed 42. Features use only the first 600 seconds of discharge plus cycle number. Full-cycle capacity, elapsed full-discharge duration, future cycles and EOL labels are excluded from inputs.',
        '', '| Task | Test MAE | Test RMSE | Constant baseline MAE |', '|---|---:|---:|---:|',
        *[f"| {task.upper()} ({m['units']}) | {m['mae']:.3f} | {m['rmse']:.3f} | {m['constant_baseline_mae']:.3f} |" for task,m in metrics.items()],
        '',report['limitations'],'','SOH is capacity / first observed capacity. RUL is evaluated only through the first observed crossing; post-EOL rows remain in the replay but are not included in RUL metrics.',
        '', 'No third-party pickle/joblib was loaded. Our trained forests are exported as JSON and run in the server using standard Python.',
        '', '![ML replay dashboard](dashboard-ml.png)','', '[Prediction CSV](ml-cycle-predictions.csv) · [Metrics and replay JSON](ml-results.json)',
        '', 'Reproduce: `python -m pip install -r requirements-ml.txt` then `python -B train_ml.py`.']),encoding='utf-8')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,default=Path('data/nasa-discharge.csv'))
    args=parser.parse_args()
    train(args.raw,Path('results'),Path('models/nasa-forest.json'))
