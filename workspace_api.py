"""HTTP routing for the local project workspace (no external writes)."""
from urllib.parse import parse_qs
import lifecycle


def get(store,url):
    path=url.path
    if path=='/api/workspace/lifecycle':return lifecycle.dashboard(store,parse_qs(url.query).get('project',[''])[0])
    if path=='/api/workspace/schema':return store.schema()
    if path=='/api/workspace/dashboard':
        query=parse_qs(url.query)
        project=query.get('project',[''])[0]
        ids=query.get('experiments',[None])[0]
        return store.dashboard(project,ids.split(',') if ids else None)
    if path.startswith('/api/workspace/designs/'):
        design_id=path.rsplit('/',1)[-1]
        return store.context(design_id)
    if path.startswith('/api/workspace/experiments/'):
        return store.experiment(path.rsplit('/',1)[-1])
    raise ValueError('Unknown workspace endpoint')


def post(store,path,data):
    if path.startswith('/api/workspace/lifecycle/'):
        return lifecycle.api(store,path.rsplit('/',1)[-1],data)
    if path=='/api/workspace/designs':return store.save_design(data)
    if path=='/api/workspace/experiments':return store.start(data)
    parts=path.strip('/').split('/')
    if len(parts)==5 and parts[:3]==['api','workspace','issues'] and parts[4]=='resolve':return store.resolve(parts[3],data)
    raise ValueError('Unknown workspace endpoint')
