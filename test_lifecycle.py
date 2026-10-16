import tempfile
import unittest
from pathlib import Path
from project_store import ProjectStore
from cell_spec import template
import lifecycle as lc

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ProjectStore(Path(self.tmp.name)/'store.db');self.pid='prismatic-lfp01'
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def save(self,kind,**kw):return lc.api(self.store,'create',dict(kind=kind,project_id=self.pid,**kw))
    def chain(self):
        d=self.save('doe',code='D1',revision=1,owner='R&D',objective='Test',bom=template(self.pid))
        b=self.save('batch',doe_id=d['id'],code='B1',owner='Pilot')
        c=self.save('cell',batch_id=b['id'],code='C1')
        t=self.save('test',cell_id=c['id'],code='T1',equipment='E1',channel='1',protocol='CC',status='queued')
        return d,b,c,t
    def cycle(self,n,temp=25):return dict(cycle=n,charge_ah=2.5,discharge_ah=2.4,dcir_mohm=30,temperature_c=temp)
    def test_demo_idempotent_and_isolated(self):
        self.assertTrue(lc.api(self.store,'demo',{})['created']);self.assertFalse(lc.api(self.store,'demo',{})['created'])
        for pid in ['prismatic-lfp01','prismatic-sib','cylindrical-lfp01','cylindrical-sib']:
            d=lc.dashboard(self.store,pid);self.assertEqual(len(d['tests']),6)
            self.assertEqual(sum(t['status']=='stopped' for t in d['tests']),2)
            self.assertTrue(all(t['source']=='demo' for t in d['tests']))
            self.assertTrue(all(t['ml'] is None for t in d['tests']) if 'sib' in pid else all(t['ml']['experimental'] for t in d['tests']))
    def test_revision_immutable(self):
        d,_,_,_=self.chain()
        with self.assertRaises(ValueError):self.save('doe',code='D1',revision=1,owner='Other',objective='Change',bom=template(self.pid))
        bom=template(self.pid);bom['cell']['energy_density']=200
        self.save('doe',code='D1',revision=2,owner='Other',objective='Change',bom=bom)
        self.assertEqual(lc.dashboard(self.store,self.pid)['records'][0]['bom'],d['bom'])
    def test_append_stop_and_preserve_after_resolve(self):
        _,_,_,t=self.chain()
        lc.api(self.store,'append',dict(id=t['id'],cycles=[self.cycle(1),self.cycle(2,51)]))
        dash=lc.dashboard(self.store,self.pid);self.assertEqual(dash['tests'][0]['status'],'stopped')
        issue=next(r for r in dash['records'] if r['kind']=='issue')
        lc.api(self.store,'resolve',dict(id=issue['id'],resolution='Investigated'))
        self.assertEqual(lc.dashboard(self.store,self.pid)['tests'][0]['status'],'stopped')
        with self.assertRaises(ValueError):lc.api(self.store,'append',dict(id=t['id'],cycles=[self.cycle(3)]))
    def test_links_and_mixed_sources_rejected(self):
        d,b,c,t=self.chain()
        with self.assertRaises(ValueError):self.save('cell',batch_id=b['id'],code='Bad',source='demo')
        with self.assertRaises(ValueError):self.save('batch',doe_id=c['id'],code='Bad',owner='x')
    def test_duplicate_cycle_rolls_back(self):
        _,_,_,t=self.chain();lc.api(self.store,'append',dict(id=t['id'],cycles=[self.cycle(1)]))
        with self.assertRaises(ValueError):lc.api(self.store,'append',dict(id=t['id'],cycles=[self.cycle(1)]))
        self.assertEqual(len(lc.dashboard(self.store,self.pid)['tests'][0]['cycles']),1)
    def test_channel_conflict_and_persistence(self):
        _,_,c,t=self.chain();lc.api(self.store,'append',dict(id=t['id'],cycles=[self.cycle(1)]))
        with self.assertRaises(ValueError):self.save('test',cell_id=c['id'],code='T2',equipment='E1',channel='1',protocol='CC',status='running')
        other=ProjectStore(self.store.path)
        try:self.assertEqual(len(lc.dashboard(other,self.pid)['tests']),1)
        finally:other.close()
if __name__=='__main__':unittest.main()
