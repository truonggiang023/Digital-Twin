"""Traceable lifecycle registry. Demo data is explicit and never hardware telemetry."""
import csv
import io
import json
import math
import time
import uuid
from cell_spec import PROJECTS, project, template, normalize

KINDS=('doe','batch','cell','test','issue')

def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS lifecycle(kind TEXT,id TEXT PRIMARY KEY,project_id TEXT,body TEXT)')

def records(db):
    init(db)
    return [json.loads(r['body']) for r in db.execute('SELECT body FROM lifecycle ORDER BY rowid')]

def text(value,name,limit=200):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('Required text: '+name)
    return value.strip()

def save(db,kind,data):
    if kind not in KINDS or not isinstance(data,dict):raise ValueError('Invalid registry record')
    rows=records(db);lookup={r['id']:r for r in rows}
    pid=data.get('project_id');project(pid)
    source=data.get('source','manual')
    if source not in ('manual','demo'):raise ValueError('Source must be manual or demo')
    row=dict(id=uuid.uuid4().hex,kind=kind,project_id=pid,source=source,created=time.time())
    def parent(key,expected):
        p=lookup.get(data.get(key))
        if not p or p['kind']!=expected or p['project_id']!=pid:raise ValueError('Invalid same-project link: '+key)
        if p['source']!=source:raise ValueError('Cannot mix demo and manual records')
        row[key]=p['id'];return p
    if kind=='doe':
        for key in ('code','objective','owner'):row[key]=text(data.get(key),key)
        row['revision']=data.get('revision')
        if type(row['revision'])!=int or row['revision']<1:raise ValueError('Revision must be a positive integer')
        if any(r['kind']=='doe' and r['project_id']==pid and r['code']==row['code'] and r['revision']==row['revision'] for r in rows):raise ValueError('DOE code/revision already exists; create next revision')
        from cell_spec import FIELDS
        bom=data.get('bom',{})
        if not isinstance(bom,dict) or any(not isinstance(bom.get(g),dict) or set(bom[g])!=set(fs) for g,fs in FIELDS.items()):raise ValueError('Provide all original BOM fields explicitly')
        row['bom']=normalize(pid,bom)
    elif kind=='batch':
        parent('doe_id','doe');row['code']=text(data.get('code'),'Batch ID');row['owner']=text(data.get('owner'),'Owner')
    elif kind=='cell':
        b=parent('batch_id','batch');row['doe_id']=b['doe_id'];row['code']=text(data.get('code'),'Cell ID')
        if any(r['kind']=='cell' and r['project_id']==pid and r['code']==row['code'] for r in rows):raise ValueError('Cell ID already exists')
    elif kind=='test':
        c=parent('cell_id','cell');row.update(batch_id=c['batch_id'],doe_id=c['doe_id'])
        for key in ('code','equipment','channel','protocol'):row[key]=text(data.get(key),key)
        row['status']=data.get('status','queued')
        if row['status'] not in ('queued','running','completed','stopped'):raise ValueError('Invalid test status')
        if row['status']=='running' and any(r['kind']=='test' and r['status']=='running' and r['equipment']==row['equipment'] and r['channel']==row['channel'] for r in rows):raise ValueError('Equipment channel is already occupied')
        row['cycles']=validate_cycles(data.get('cycles',[]))
        row['ml']=None
        if source=='demo' and row['cycles'] and project(pid)['chemistry']=='LFP':
            from ml_inference import predict,model
            features={k:sum(model()['bounds'][k])/2 for k in model()['features']}
            features['cycle']=row['cycles'][-1]['cycle']
            row['ml']=dict(predict(features),features=features,experimental=True,valid_for_hardware=False,input_source='synthetic illustrative features, not extracted from measurements')
        if row['status']!='stopped' and any(c['temperature_c']>=45 for c in row['cycles']):raise ValueError('Temperature ≥45°C requires stopped status and reason')
        row['stop_reason']=text(data.get('stop_reason'),'stop_reason') if row['status']=='stopped' else ''
    else:
        t=parent('test_id','test');row.update(cell_id=t['cell_id'],batch_id=t['batch_id'],doe_id=t['doe_id'])
        for key in ('title','owner','due_date'):row[key]=text(data.get(key),key)
        from datetime import date
        try:date.fromisoformat(row['due_date'])
        except ValueError:raise ValueError('Due date must be YYYY-MM-DD')
        row['severity']=data.get('severity','warning')
        if row['severity'] not in ('info','warning','critical'):raise ValueError('Invalid severity')
        row.update(status='open',resolution='')
    db.execute('INSERT INTO lifecycle VALUES(?,?,?,?)',(kind,row['id'],pid,json.dumps(row)))
    return row

def validate_cycles(rows):
    if not isinstance(rows,list) or len(rows)>5000:raise ValueError('Maximum 5000 cycle rows')
    result=[];previous=0
    for r in rows:
        if not isinstance(r,dict):raise ValueError('Invalid cycle row')
        clean={}
        for key,lo,hi in [('cycle',1,100000),('charge_ah',.00001,10000),('discharge_ah',.00001,10000),('dcir_mohm',0,100000),('temperature_c',-50,150)]:
            v=r.get(key)
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid cycle field: '+key)
            clean[key]=v
        if int(clean['cycle'])!=clean['cycle'] or clean['cycle']<=previous:raise ValueError('Cycles must increase, no duplicates')
        previous=clean['cycle'];result.append(clean)
    return result

def api(store,method,data):
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE');init(db)
        if method=='create':return save(db,data.get('kind'),data)
        if method=='demo':
            if any(r['source']=='demo' for r in records(db)):return dict(created=False,note='Demo already exists; existing records preserved')
            for p in PROJECTS:
                pid=p['id']
                for variant in range(2):
                    doe=save(db,'doe',dict(project_id=pid,source='demo',code='DEMO-'+p['code']+'-'+str(variant+1),revision=1,owner='Demo R&D',objective='Compare retention and temperature; example design',bom=template(pid)))
                    batch=save(db,'batch',dict(project_id=pid,source='demo',doe_id=doe['id'],code='BATCH-'+str(variant+1),owner='Demo Pilot Line'))
                    for n in range(3):
                        cell=save(db,'cell',dict(project_id=pid,source='demo',batch_id=batch['id'],code='DEMO-'+str(variant+1)+'-CELL-'+str(n+1)))
                        status=['running','completed','stopped'][n];cycles=[]
                        for cycle in range(1,61+variant*20):
                            q=2.5*(1-(.0006+variant*.0003+n*.0001)*cycle)
                            cycles.append(dict(cycle=cycle,charge_ah=q/.995,discharge_ah=q,dcir_mohm=30+cycle*.08+n*2,temperature_c=27+variant*2+n+cycle*.03))
                        if status=='stopped':cycles[-1]['temperature_c']=51
                        t=save(db,'test',dict(project_id=pid,source='demo',cell_id=cell['id'],code='TEST-'+cell['code'],equipment='DEMO-'+pid,channel=str(variant*3+n+1),protocol='CC/CV 0.33C charge, 1C discharge; synthetic cycle summary',status=status,cycles=cycles,stop_reason='Overtemperature 51°C · DEMO' if status=='stopped' else ''))
                        if n==2:save(db,'issue',dict(project_id=pid,source='demo',test_id=t['id'],title='Overtemperature: STOP latched in demo record',owner='Demo Test Engineer',due_date='2026-10-23',severity='critical'))
            return dict(created=True)
        if method=='append':
            row=next((r for r in records(db) if r['id']==data.get('id') and r['kind']=='test'),None)
            if not row or row['source']!='manual':raise ValueError('Only manual tests accept cycle imports')
            if row['status'] in ('stopped','completed'):raise ValueError('Test is closed; create a new test for retest')
            added=validate_cycles(data.get('cycles',[]))
            if not added:raise ValueError('Provide at least one cycle')
            row['cycles']=validate_cycles(row['cycles']+added)
            row['status']='running'
            if any(c['temperature_c']>=45 for c in added):
                row.update(status='stopped',stop_reason='Imported cycle temperature ≥45°C. Registry STOP only; no equipment command sent.')
                save(db,'issue',dict(project_id=row['project_id'],source='manual',test_id=row['id'],title=row['stop_reason'],owner='Unassigned',due_date=time.strftime('%Y-%m-%d',time.gmtime()),severity='critical'))
            db.execute('UPDATE lifecycle SET body=? WHERE id=?',(json.dumps(row),row['id']));return row
        if method=='resolve':
            row=next((r for r in records(db) if r['id']==data.get('id') and r['kind']=='issue'),None)
            if not row:raise ValueError('Issue not found')
            row.update(status='resolved',resolution=text(data.get('resolution'),'Resolution',500))
            db.execute('UPDATE lifecycle SET body=? WHERE id=?',(json.dumps(row),row['id']));return row
        raise ValueError('Unknown lifecycle action')

def dashboard(store,pid):
    project(pid)
    with store.db() as db:rows=[r for r in records(db) if r['project_id']==pid]
    lookup={r['id']:r for r in rows};tests=[]
    for r in rows:
        if r['kind']!='test':continue
        d=lookup[r['doe_id']];c=lookup[r['cell_id']];b=lookup[r['batch_id']];cycles=r['cycles'];last=cycles[-1] if cycles else None
        metrics=None
        if last:
            metrics=dict(capacity_ah=last['discharge_ah'],retention_percent=100*last['discharge_ah']/cycles[0]['discharge_ah'],soh_percent=100*last['discharge_ah']/d['bom']['cell']['capacity_033_typical'],dcir_mohm=last['dcir_mohm'],ce_percent=100*last['discharge_ah']/last['charge_ah'],temperature_c=last['temperature_c'])
        passed=None if not metrics else metrics['capacity_ah']>=d['bom']['cell']['capacity_033_min'] and metrics['temperature_c']<45 and r['status']!='stopped'
        tests.append(dict(r,doe_code=d['code'],revision=d['revision'],cell_code=c['code'],batch_code=b['code'],metrics=metrics,target_pass=passed,target_scope='capacity minimum and temperature <45°C only; energy/mass targets not evaluated'))
    return dict(project=project(pid),records=rows,tests=tests,source_note='Demo records are synthetic snapshots; running is a scenario label, not hardware connection. Manual entries are user-supplied, not verified measurements.')
