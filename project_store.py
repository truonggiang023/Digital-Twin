"""Local SQLite workspace for design sheets, asynchronous DOE samples and issues."""
import copy
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cell_spec import PROJECTS,FIELDS,project,template,normalize,inspect,assess,effective_sheet
from doe import prepare,evaluate,analyze,digest
import random


class ProjectStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='project-doe')
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS designs(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,revision INTEGER,bom TEXT,validation TEXT,created REAL,updated REAL);
            CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,project_id TEXT,design_id TEXT,revision INTEGER,name TEXT,status TEXT,config TEXT,sheet TEXT,meta TEXT,created REAL,updated REAL);
            CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY,experiment_id TEXT,run_id TEXT,status TEXT,run_order INTEGER,summary TEXT,curve TEXT);
            CREATE TABLE IF NOT EXISTS issues(id TEXT PRIMARY KEY,project_id TEXT,design_id TEXT,experiment_id TEXT,sample_id TEXT,code TEXT,title TEXT,severity TEXT,status TEXT,origin TEXT,created REAL,updated REAL,resolution TEXT);
            CREATE INDEX IF NOT EXISTS samples_experiment ON samples(experiment_id);
            CREATE INDEX IF NOT EXISTS issues_project ON issues(project_id,status);
            ''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(str(self.path),timeout=15);db.row_factory=sqlite3.Row
        try:
            yield db;db.commit()
        except Exception:
            db.rollback();raise
        finally:db.close()

    def schema(self):
        return dict(projects=PROJECTS,fields=FIELDS,groups=['cell','cathode','anode','assembly','formation'],
                    templates={p['id']:template(p['id']) for p in PROJECTS},data_origin='synthetic_doe',
                    note='Example templates, not production specifications. Form factor and recorded-only BOM fields are not calibrated model inputs.')

    def _issue(self,db,project_id,design_id,experiment_id,sample_id,code,title,severity,origin):
        key=digest(dict(design=design_id,experiment=experiment_id,sample=sample_id,code=code));now=time.time()
        db.execute('''INSERT INTO issues VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET title=excluded.title,severity=excluded.severity,status='open',updated=excluded.updated,resolution='' ''',
            (key,project_id,design_id,experiment_id,sample_id,code,title,severity,'open',origin,now,now,''))

    def save_design(self,data):
        if not isinstance(data,dict) or set(data)-{'id','project_id','name','bom','revision'}:raise ValueError('Invalid design fields')
        project_id=data.get('project_id');project(project_id)
        name=data.get('name','')
        if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Design name is required, max 80 characters')
        bom=normalize(project_id,data.get('bom',{}));validation=inspect(project_id,bom)
        now=time.time();design_id=data.get('id') or uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT * FROM designs WHERE id=?',(design_id,)).fetchone()
            if data.get('id') and not current:raise ValueError('Unknown design')
            if current and (current['project_id']!=project_id or data.get('revision')!=current['revision']):raise ValueError('Design changed; refresh before saving')
            revision=current['revision']+1 if current else 1
            db.execute('INSERT OR REPLACE INTO designs VALUES(?,?,?,?,?,?,?,?)',
                       (design_id,project_id,name.strip(),revision,json.dumps(bom),json.dumps(validation),current['created'] if current else now,now))
            db.execute("UPDATE issues SET status='resolved',resolution='Revalidated after design edit',updated=? WHERE design_id=? AND origin='design_validation' AND status='open'",(now,design_id))
            for issue in validation['issues']:
                self._issue(db,project_id,design_id,None,None,issue['code'],issue['title'],issue['severity'],'design_validation')
        return self.get_design(design_id)

    def get_design(self,design_id):
        with self.db() as db:row=db.execute('SELECT * FROM designs WHERE id=?',(design_id,)).fetchone()
        if not row:raise ValueError('Design not found')
        result=dict(row);result['bom']=json.loads(result['bom']);result['validation']=json.loads(result['validation']);result['project']=project(result['project_id'])
        return result

    def context(self,design_id):
        design=self.get_design(design_id)
        p=design['project']
        return dict(design=design,baseline=design['validation']['baseline'],
                    default_vary={'np_ratio':[1.05,1.2],'cathode_loading_mg_cm2':[12,24]},
                    allowed_cathodes=['NFPP'] if p['chemistry']=='sodium-ion' else ['LFP'],
                    allowed_anodes=['HardCarbon'] if p['chemistry']=='sodium-ion' else ['Graphite','Si-Graphite','LTO'],
                    allowed_electrolytes=['NaPF6-carbonate','NaFSI-ether'] if p['chemistry']=='sodium-ion' else ['LiPF6-EC-EMC','LiPF6-FEC','LiFSI-ether'])

    def start(self,data):
        if not isinstance(data,dict) or set(data)-{'design_id','config','name'}:raise ValueError('Invalid experiment fields')
        design=self.get_design(data.get('design_id'))
        if not design['validation']['simulation_supported']:raise ValueError('Fix blocking cell-sheet issues before running')
        config=data.get('config',{})
        if not isinstance(config,dict):raise ValueError('Invalid DOE config')
        config=dict(config);config['baseline']=dict(design['validation']['baseline'],**config.get('baseline',{}))
        clean,report=prepare(config)
        context=self.context(design['id'])
        for row in report['runs']:
            p=row['inputs']
            if p['cathode'] not in context['allowed_cathodes'] or p['anode'] not in context['allowed_anodes'] or p['electrolyte'] not in context['allowed_electrolytes']:
                raise ValueError('DOE material family does not match the selected project')
        name=data.get('name') or design['name']+' DOE'
        if not isinstance(name,str) or len(name)>100:raise ValueError('Invalid experiment name')
        experiment_id=uuid.uuid4().hex;now=time.time()
        report['project_context']=dict(project=design['project'],worksheet_id=design['id'],revision=design['revision'],name=design['name'],bom=design['bom'])
        meta={k:v for k,v in report.items() if k!='runs'}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute("SELECT COUNT(*) FROM experiments WHERE status IN ('queued','running')").fetchone()[0]
            if active>=2:raise ValueError('Two experiments are active; wait for one to finish')
            count=db.execute('SELECT COUNT(*) FROM experiments WHERE project_id=?',(design['project_id'],)).fetchone()[0]
            if count>=100:raise ValueError('Project history limit reached (100 experiments); export results. Automatic archival is not implemented.')
            db.execute('INSERT INTO experiments(id,project_id,design_id,revision,name,status,config,sheet,meta,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (experiment_id,design['project_id'],design['id'],design['revision'],name,'queued',json.dumps(clean),json.dumps(design['bom']),json.dumps(meta),now,now))
            for row in report['runs']:
                summary=dict(row,status='planned',reason='',metrics=None,assessment=None)
                db.execute('INSERT INTO samples VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,experiment_id,row['run_id'],'planned',row['run_order'],json.dumps(summary),'[]'))
        self.executor.submit(self._run,experiment_id,design,clean)
        return dict(id=experiment_id,status='queued',project_id=design['project_id'])

    def _run(self,experiment_id,design,config):
        try:
            with self.db() as db:
                db.execute("UPDATE experiments SET status='running',updated=? WHERE id=?",(time.time(),experiment_id))
                samples=[dict(r) for r in db.execute('SELECT * FROM samples WHERE experiment_id=? ORDER BY run_order',(experiment_id,))]
            rows=[]
            for sample in samples:
                row=json.loads(sample['summary'])
                with self.db() as db:db.execute("UPDATE samples SET status='running' WHERE id=?",(sample['id'],))
                rng=random.Random(int(digest(dict(seed=config['seed'],run_id=row['run_id'])),16))
                try:
                    metrics=evaluate(row['inputs'],config['cycles'],rng,config['variation_percent'])
                    curve=metrics.pop('curve');row.update(status=metrics['status'],reason=metrics['reason'],metrics=metrics)
                except ValueError as error:
                    curve=[];row.update(status='infeasible',reason=str(error),metrics=None)
                targets=copy.deepcopy(design['bom']);targets['cell']['energy_density']=row['inputs']['energy_density_target_wh_kg']
                row['assessment']=assess(targets,row['metrics'],row['status']);rows.append(row)
                with self.db() as db:
                    db.execute('UPDATE samples SET status=?,summary=?,curve=? WHERE id=?',(row['status'],json.dumps(row),json.dumps(curve),sample['id']))
                    db.execute('UPDATE experiments SET updated=? WHERE id=?',(time.time(),experiment_id))
                    if row['status']!='completed':
                        self._issue(db,design['project_id'],design['id'],experiment_id,sample['id'],'cell_fault',row['reason'],'error','execution')
                    elif not row['assessment']['passed']:
                        missing=', '.join(k for k,v in row['assessment']['checks'].items() if not v)
                        self._issue(db,design['project_id'],design['id'],experiment_id,sample['id'],'target_miss','Cell failed targets: '+missing,'warning','performance')
            with self.db() as db:
                current=db.execute('SELECT meta FROM experiments WHERE id=?',(experiment_id,)).fetchone()
                meta=json.loads(current['meta']);meta['effects']=analyze(rows,config['vary'])
                meta['summary']={s:sum(r['status']==s for r in rows) for s in ['completed','stopped','infeasible']}
                meta['summary']['energy_target_met']=sum(r['status']=='completed' and r['metrics']['energy_target_met'] for r in rows)
                meta['analysis_note']='Synthetic model only. Detailed recorded BOM fields and form factor are not calibrated causal inputs. Target pass requires energy, capacities, weight and voltage checks.'
                from doe import schema
                meta.update(assumptions=schema()['assumptions'],factor_schema=schema()['factors'],metric_labels=schema()['metrics'])
                db.execute("UPDATE experiments SET status='completed',meta=?,updated=? WHERE id=?",(json.dumps(meta),time.time(),experiment_id))
        except Exception as error:
            with self.db() as db:
                db.execute("UPDATE experiments SET status='failed',updated=? WHERE id=?",(time.time(),experiment_id))
                db.execute("UPDATE samples SET status='interrupted' WHERE experiment_id=? AND status IN ('planned','running')",(experiment_id,))
                self._issue(db,design['project_id'],design['id'],experiment_id,None,'execution_failed','Execution failed: '+type(error).__name__,'error','execution')

    def experiment(self,experiment_id):
        with self.db() as db:
            row=db.execute('SELECT * FROM experiments WHERE id=?',(experiment_id,)).fetchone()
            if not row:raise ValueError('Experiment not found')
            result={k:row[k] for k in ['id','project_id','design_id','revision','name','status','created','updated']}
            result['counts']={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM samples WHERE experiment_id=? GROUP BY status',(experiment_id,))}
            result['sheet']=json.loads(row['sheet'])
            result['report']=None
            if row['status']=='completed':
                report=json.loads(row['meta']);report['workspace_experiment_id']=experiment_id
                report['runs']=[]
                for sample in db.execute('SELECT * FROM samples WHERE experiment_id=? ORDER BY run_order',(experiment_id,)):
                    run=json.loads(sample['summary'])
                    run['effective_bom']=effective_sheet(result['sheet'],run['inputs'])
                    if run['metrics'] is not None:run['metrics']['curve']=json.loads(sample['curve'])
                    report['runs'].append(run)
                result['report']=report
            return result

    def resolve(self,issue_id,data):
        note=data.get('resolution','') if isinstance(data,dict) else ''
        if not isinstance(note,str) or not 1<=len(note.strip())<=500:raise ValueError('Resolution note required (max 500 characters)')
        with self.db() as db:
            if not db.execute('SELECT id FROM issues WHERE id=?',(issue_id,)).fetchone():raise ValueError('Issue not found')
            db.execute("UPDATE issues SET status='resolved',resolution=?,updated=? WHERE id=?",(note.strip(),time.time(),issue_id))
        return dict(id=issue_id,status='resolved')

    def dashboard(self,project_id,experiment_ids=None):
        project(project_id);now=time.time()
        with self.db() as db:
            # No fabricated running count after a crashed process. Work is bounded per sample.
            stale=db.execute("SELECT * FROM experiments WHERE project_id=? AND status IN ('queued','running') AND updated<?",(project_id,now-120)).fetchall()
            for row in stale:
                db.execute("UPDATE experiments SET status='interrupted' WHERE id=?",(row['id'],))
                db.execute("UPDATE samples SET status='interrupted' WHERE experiment_id=? AND status IN ('planned','running')",(row['id'],))
                self._issue(db,project_id,row['design_id'],row['id'],None,'interrupted','Experiment heartbeat expired; rerun required.','error','execution')
            designs=[]
            for row in db.execute('SELECT * FROM designs WHERE project_id=? ORDER BY updated DESC',(project_id,)):
                value=dict(row);value['bom']=json.loads(value['bom']);value['validation']=json.loads(value['validation']);designs.append(value)
            experiments=[]
            for row in db.execute('SELECT * FROM experiments WHERE project_id=? ORDER BY created DESC',(project_id,)):
                record={k:row[k] for k in ['id','name','design_id','revision','status','created','updated']};record['cycles']=json.loads(row['config'])['cycles']
                summaries=[dict(json.loads(s['summary']),status=s['status']) for s in db.execute('SELECT summary,status FROM samples WHERE experiment_id=?',(row['id'],))]
                good=[r['metrics'] for r in summaries if r['status']=='completed']
                record.update(cells=len(summaries),passed=sum(bool(r.get('assessment',{}).get('passed')) for r in summaries if r['status']=='completed' and r.get('assessment')),
                              faults=sum(r['status'] in ('stopped','infeasible','interrupted') for r in summaries),
                              mean_energy=sum(m['specific_energy_wh_kg'] for m in good)/len(good) if good else None,
                              mean_soh=sum(m['soh_final_percent'] for m in good)/len(good) if good else None)
                experiments.append(record)
            selected=experiment_ids or [e['id'] for e in experiments[:4]]
            if not isinstance(selected,list) or len(selected)>4 or set(selected)-{e['id'] for e in experiments}:raise ValueError('Select up to four experiments in this project')
            cells=[]
            for experiment_id in selected:
                for sample in db.execute('SELECT * FROM samples WHERE experiment_id=? ORDER BY run_order',(experiment_id,)):
                    cell=json.loads(sample['summary']);cell.update(sample_id=sample['id'],experiment_id=experiment_id,status=sample['status']);cells.append(cell)
            issues=[dict(r) for r in db.execute('''SELECT issues.*,samples.run_order AS cell_number,
                experiments.name AS experiment_name,designs.name AS design_name FROM issues
                LEFT JOIN samples ON samples.id=issues.sample_id
                LEFT JOIN experiments ON experiments.id=issues.experiment_id
                LEFT JOIN designs ON designs.id=issues.design_id
                WHERE issues.project_id=? ORDER BY issues.created DESC''',(project_id,))]
            counts=dict(total=len(cells),running=sum(r['status']=='running' for r in cells),
                        queued=sum(r['status']=='planned' for r in cells),completed=sum(r['status']=='completed' for r in cells),
                        faults=sum(r['status'] in ('stopped','infeasible','interrupted') for r in cells),
                        target_pass=sum(bool(r['status']=='completed' and r['assessment'] and r['assessment']['passed']) for r in cells),
                        target_miss=sum(bool(r['status']=='completed' and r['assessment'] and r['assessment']['state']=='target_miss') for r in cells),
                        open_issues=sum(r['status']=='open' for r in issues))
        return dict(project=project(project_id),designs=designs,experiments=experiments,selected_experiments=selected,
                    cells=cells,issues=issues,counts=counts,data_origin='synthetic_doe',physical_cycler_connected=False)

    def close(self):self.executor.shutdown(wait=True)
