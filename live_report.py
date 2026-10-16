"""DOE demo metadata joined to the actual in-memory 12-channel simulator."""
from datetime import datetime,timezone
from cell_spec import template


def report(rack):
    # Caller holds rack.lock: telemetry, ML and histories form one consistent snapshot.
    does=[]
    for group in range(4):
        pid='prismatic-lfp01' if group<2 else 'cylindrical-lfp01'
        bom=template(pid)
        bom['cell']['capacity_033_typical']=2.5+.025*(group*3+1)
        bom['cell']['capacity_033_min']=bom['cell']['capacity_033_typical']*.95
        does.append(dict(project_id=pid,form_factor='PRISMATIC' if group<2 else 'CYLINDRICAL',id='LIVE-DOE-%02d'%(group+1),revision=1,owner='Demo R&D',
            objective='Monitor three live simulator channels; no causal design effect claimed',bom=bom))
    tests=[]
    for index,c in enumerate(rack.cells):
        d=does[index//3]
        tests.append(dict(project_id=c['project_id'],form_factor=c['form_factor'],source='live_cycler_simulator',session_id=rack.session_id,
            doe_id=d['id'],revision=d['revision'],batch_id='LIVE-BATCH-%02d'%(index//3+1),
            cell_id='LIVE-CELL-%02d'%c['id'],test_id=rack.session_id+'-CH%02d'%c['id'],
            equipment='SIM-RACK-01',channel=c['id'],protocol='CC/CV 2A 4.2V → rest → discharge 2A 3.0V; 3 cycles',
            telemetry=dict(c),run_state='running' if rack.running and c['status']=='running' else
                ('paused' if not rack.running and c['status']=='running' else c['status']),
            target_state='fault' if c['status'] in ('fault','stopped') else 'pending_complete_cycle',
            metric_basis=dict(capacity_ah='Model usable capacity, not completed discharge measurement',
                resistance_mohm='Model resistance, not pulse-measured DCIR',stage_capacity_ah='Partial current-stage throughput',
                ce_percent='Unavailable: complete paired charge/discharge cycles not aggregated'),
            ce_percent=None))
    return dict(exported_at=datetime.now(timezone.utc).isoformat(),session_id=rack.session_id,
                source='live_cycler_simulator',running=rack.running,safety_stop=rack.safety_stop,
                alarms=list(rack.alarms),does=does,tests=tests,
                note='DOE recipes are demo metadata only. Simulator uses generic 3.0–4.2V OCV, not calibrated LFP physics. No SIB data is claimed. Reset creates a new test session; snapshots do not persist runtime telemetry.')
