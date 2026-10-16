"""Reproduce a DOE from a configuration or an exported report JSON."""
import argparse
import csv
import json
from pathlib import Path
from doe import run_experiment, FACTORS, METRICS


def export(config,output):
    report=run_experiment(config)
    output.mkdir(parents=True,exist_ok=True)
    (output/'doe-results.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    headers=['experiment_id','model_version','data_origin','calibrated','seed','cycles','variation_percent',
             'design_id','run_id','run_order','replicate','ml_split','status','reason',*FACTORS,*METRICS,
             'energy_target_met','eol_censored','completed_cycles','cell_mass_g','cathode_porosity','cathode_thickness_um']
    with (output/'doe-results.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.DictWriter(file,fieldnames=headers,extrasaction='ignore');writer.writeheader()
        for row in report['runs']:
            values=dict(experiment_id=report['experiment_id'],model_version=report['model_version'],
                        data_origin=report['data_origin'],calibrated=False,seed=report['config']['seed'],
                        cycles=report['config']['cycles'],variation_percent=report['config']['variation_percent'],**row)
            values.update(row['inputs']);values.update(row['metrics'] or {})
            values={k:('true' if v else 'false') if isinstance(v,bool) else v for k,v in values.items()}
            writer.writerow(values)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path,default=Path('doe-output'))
    args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    result=export(config.get('config',config),args.output)
    print(f"DOE {result['experiment_id']}: {result['run_count']} runs; {result['summary']}; saved to {args.output}")
