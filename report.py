"""Generate a reproducible model-only cycling and degradation report."""
import argparse
import csv
import json
from pathlib import Path
from aging import forecast
from main import Battery, simulate


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    cells, cycle_rows, predictions = [], [], []
    for i in range(12):
        b = Battery(capacity_ah=2.5+0.025*i, resistance_ohm=0.07+0.004*i,
                    soc=0.15+0.025*i, temperature_c=25+0.2*i, ambient_c=25+0.2*i)
        peak = b.temperature_c
        discharges = {}
        for row in simulate(b, cycles=3, current_a=2):
            peak = max(peak, row['temperature_c'])
            if row['stage'] == 'discharge':
                discharges[row['cycle']] = row.copy()
        for cycle, end in discharges.items():
            cycle_rows.append(dict(cell=i+1, cycle=cycle, discharge_ah=end['stage_capacity_ah'],
                                   end_voltage_v=end['voltage_v'], soh_percent=end['soh_percent'],
                                   efc=end['efc']))
        health = dict(cell=i+1, status='complete', cycles=3, time_s=row['time_s'],
                      peak_temperature_c=peak, final_soc_percent=100*b.soc, **b.health())
        cells.append(health)
        for name, temperature, rate in [('baseline',25,1), ('warm',35,1), ('fast',25,2)]:
            prediction = forecast(b.capacity_ah, b.resistance_ohm, b.soh, b.efc,
                                  temperature_c=temperature, c_rate=rate, dod=0.8)
            predictions.append(dict(cell=i+1, name=name, **prediction))
    result = dict(source='local-model', calibrated=False, batterytwin_api_connected=False,
                  current_a=2, cycles_per_cell=3, cells=cells, predictions=predictions)
    (output/'aging-results.json').write_text(json.dumps(result,indent=2), encoding='utf-8')
    with (output/'cycle-summary.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(cycle_rows[0]));writer.writeheader();writer.writerows(cycle_rows)
    with (output/'degradation-predictions.csv').open('w',newline='',encoding='utf-8') as file:
        fields=['cell','scenario','temperature_c','c_rate','dod','eol_soh','cycle','efc','soh_percent',
                'capacity_ah','resistance_mohm','optimistic_soh_percent','pessimistic_soh_percent']
        writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader()
        for prediction in predictions:
            for point in prediction['points']:
                writer.writerow(dict(cell=prediction['cell'],scenario=prediction['name'],
                                     **{k:prediction['scenario'][k] for k in ['temperature_c','c_rate','dod','eol_soh']},**point))
    lines=['# Cycling and degradation results', '',
           'Source: local illustrative model. Not calibrated; BatteryTwin API is not connected.', '',
           '12 cells, three CC/CV charge/discharge cycles each at 2 A, with 60-second rests.',
           'Forecasts assume 80% DoD, a constant operating temperature/C-rate, and 80% SOH EOL.', '',
           '| Cell | Final SOH (%) | EFC | Peak temperature (°C) | Baseline RUL (cycles) | Warm 35 °C RUL | Fast 2C RUL |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for i,c in enumerate(cells):
        rul=[p['remaining_cycles'] for p in predictions if p['cell']==i+1]
        lines.append(f"| CH {i+1:02d} | {c['soh_percent']:.4f} | {c['efc']:.3f} | {c['peak_temperature_c']:.2f} | {rul[0]:.0f} | {rul[1]:.0f} | {rul[2]:.0f} |")
    lines += ['', 'RUL is additional operational cycles from the post-run health state. Each forecast',
              'cycle is 0.8 EFC. Sensitivity curves use ±30% aging rate and are not statistical',
              'confidence intervals. No calendar aging, chemistry-specific effects or trained AI model.', '',
              'Reproduce: `python -B report.py --output results`.', '',
              '![Dashboard with degradation prediction](dashboard-aging.png)', '',
              '[Cycle CSV](cycle-summary.csv) · [Forecast CSV](degradation-predictions.csv) · [JSON](aging-results.json)']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('results'))
    args=parser.parse_args()
    result=generate(args.output)
    print(f"Completed {len(result['cells'])} cells; 36 scenario forecasts saved in {args.output}")
