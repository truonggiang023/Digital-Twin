"""One canonical DOE/cell mapping shared by project workflow and live cycler."""
import json
import time
from datetime import datetime,timezone
from cell_spec import template,project


def definitions():
    result=[]
    for i in (0,6):
        pid='prismatic-lfp01' if i<6 else 'cylindrical-lfp01'
        name='DOE-P-LFP01' if i<6 else 'DOE-C-LFP01';bom=template(pid)
        bom['cell']['capacity_033_typical']=2.5+.025*i
        bom['cell']['capacity_033_min']=bom['cell']['capacity_033_typical']*.95
        result.append(dict(id=name,code=name,kind='doe',project_id=pid,source='live_cycler_simulator',
            form_factor='PRISMATIC' if i<6 else 'CYLINDRICAL',revision=1,owner='Demo R&D',
            objective='Compare six replicate cells under one design; '+name,bom=bom,created=0))
    return result


def canonical(store=None):
    defaults=definitions()
    if store is None:return defaults
    from lifecycle import init
    with store.db() as db:
        init(db)
        for d in defaults:
            db.execute('INSERT OR IGNORE INTO lifecycle VALUES(?,?,?,?)',('doe',d['id'],d['project_id'],json.dumps(d)))
        return [json.loads(db.execute('SELECT body FROM lifecycle WHERE id=?',(d['id'],)).fetchone()['body']) for d in defaults]


def report(rack,store=None,project_id=None):
    # Caller holds rack.lock: telemetry, prediction and histories are one snapshot.
    if project_id is not None:project(project_id)
    does=canonical(store);tests=[]
    for index,c in enumerate(rack.cells):
        d=does[index//6]
        if project_id is not None and d['project_id']!=project_id:continue
        tests.append(dict(id=rack.session_id+'-CH%02d'%c['id'],kind='test',
            project_id=d['project_id'],form_factor=d['form_factor'],source='live_cycler_simulator',session_id=rack.session_id,
            doe_id=d['id'],doe_name=d['code'],cell_name=d['code']+'-C%02d'%(index%6+1),revision=d['revision'],batch_id='BATCH-'+d['code'],
            cell_id='CELL-'+d['code']+'-C%02d'%(index%6+1),test_id=rack.session_id+'-CH%02d'%c['id'],
            equipment='SIM-RACK-01',channel=c['id'],protocol='CC/CV 2A 4.2V → rest → discharge 2A 3.0V; 3 cycles',
            telemetry=dict(c),run_state='running' if rack.running and c['status']=='running' else
                ('paused' if not rack.running and c['status']=='running' else c['status']),
            target_state='fault' if c['status'] in ('fault','stopped') else 'pending_complete_cycle',
            metric_basis=dict(capacity_ah='Model usable capacity, not completed discharge measurement',
                resistance_mohm='Model resistance, not pulse-measured DCIR',stage_capacity_ah='Partial current-stage throughput',
                ce_percent='Unavailable: complete paired charge/discharge cycles not aggregated'),ce_percent=None))
    channels={t['channel'] for t in tests};alarms=[dict(a) for a in rack.alarms if a['cell'] in channels]
    visible_does=[d for d in does if project_id is None or d['project_id']==project_id]
    rows=list(visible_does)
    for t in tests:
        rows.extend([dict(id=t['batch_id'],kind='batch',code=t['batch_id'],doe_id=t['doe_id'],project_id=t['project_id'],owner='Demo Pilot',source=t['source']),
                     dict(id=t['cell_id'],kind='cell',code=t['cell_name'],doe_id=t['doe_id'],batch_id=t['batch_id'],project_id=t['project_id'],channel=t['channel'],source=t['source']),t])
    issues=[]
    if store:
        with store.db() as db:
            for index,a in enumerate(rack.alarms):
                t=next((t for t in tests if t['channel']==a['cell']),None)
                if not t:continue
                key=rack.session_id+'-alarm-'+str(index)
                issue=dict(id=key,kind='issue',project_id=t['project_id'],source=t['source'],session_id=rack.session_id,
                    doe_id=t['doe_id'],cell_id=t['cell_id'],test_id=t['test_id'],channel=t['channel'],title=a['reason'],
                    severity='critical',owner='Demo Test Engineer',due_date=datetime.now(timezone.utc).date().isoformat(),
                    status='open',resolution='',created=time.time())
                db.execute('INSERT OR IGNORE INTO lifecycle VALUES(?,?,?,?)',('issue',key,t['project_id'],json.dumps(issue)))
            issues=[json.loads(r['body']) for r in db.execute("SELECT body FROM lifecycle WHERE kind='issue'")]
            issues=[i for i in issues if i['source']=='live_cycler_simulator' and (project_id is None or i['project_id']==project_id)]
    rows=list({r['id']:r for r in rows}.values())
    rows.extend(issues)
    return dict(exported_at=datetime.now(timezone.utc).isoformat(),session_id=rack.session_id,project=project(project_id) if project_id else None,
                source='live_cycler_simulator',running=rack.running,safety_stop=rack.safety_stop,
                alarms=alarms,does=visible_does,tests=tests,records=rows,issues=issues,
                note='Each cell uses its DOE name throughout the project workflow and cycler. Generic 3.0–4.2V simulation; not calibrated LFP. SIB projects have no assigned running channels. Reset starts a new session.')


def update_design(rack,store,data):
    """Edit the same canonical recipe before its channel starts, with revision history."""
    from cell_spec import normalize,FIELDS
    if not isinstance(data,dict) or set(data)-{'id','revision','owner','objective','bom'}:raise ValueError('Invalid DOE fields')
    defs=canonical(store);d=next((d for d in defs if d['id']==data.get('id')),None)
    if not d:raise ValueError('DOE not found')
    channels=range(defs.index(d)*6,defs.index(d)*6+6)
    if rack.running or any(rack.cells[channel]['time_s']>0 for channel in channels):raise ValueError('DOE has running data; export then Reset before editing the next test design')
    for key in ('owner','objective'):
        if not isinstance(data.get(key),str) or not 1<=len(data[key].strip())<=200:raise ValueError('Required: '+key)
    bom=data.get('bom')
    if not isinstance(bom,dict) or any(not isinstance(bom.get(g),dict) or set(bom[g])!=set(fs) for g,fs in FIELDS.items()):raise ValueError('Provide every original BOM field')
    bom=normalize(d['project_id'],bom)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        old=json.loads(db.execute('SELECT body FROM lifecycle WHERE id=?',(d['id'],)).fetchone()['body'])
        if data.get('revision')!=old['revision']:raise ValueError('DOE revision changed; refresh before editing')
        history=dict(old,id=old['id']+'-V'+str(old['revision']),kind='doe_revision')
        db.execute('INSERT OR IGNORE INTO lifecycle VALUES(?,?,?,?)',('doe_revision',history['id'],old['project_id'],json.dumps(history)))
        new=dict(old,revision=old['revision']+1,bom=bom,owner=data['owner'].strip(),objective=data['objective'].strip())
        db.execute('UPDATE lifecycle SET body=? WHERE id=?',(json.dumps(new),old['id']))
    return new
