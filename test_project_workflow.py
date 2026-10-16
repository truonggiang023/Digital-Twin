import tempfile
import unittest
from pathlib import Path
from server import Rack
from live_report import report,canonical,update_design
from project_store import ProjectStore
from lifecycle import api
class ProjectWorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=ProjectStore(Path(self.tmp.name)/'workspace.db');self.rack=Rack()
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_one_doe_name_per_cycler_cell_and_same_source_every_tab(self):
  d=report(self.rack,self.store,'prismatic-lfp01')
  self.assertEqual(len(d['does']),6);self.assertEqual(len(d['tests']),6)
  for t in d['tests']:
   self.assertEqual(t['cell_name'],t['doe_id']);self.assertEqual(t['telemetry']['doe_name'],t['doe_id'])
   self.assertEqual(t['telemetry'],self.rack.cells[t['channel']-1])
   self.assertTrue(any(r['kind']=='cell' and r['doe_id']==t['doe_id'] for r in d['records']))
   self.assertTrue(any(r['kind']=='batch' and r['doe_id']==t['doe_id'] for r in d['records']))
 def test_no_cross_project_or_static_demo_leak(self):
  api(self.store,'demo',{})
  d=report(self.rack,self.store,'cylindrical-lfp01')
  self.assertEqual([t['channel'] for t in d['tests']],list(range(7,13)))
  self.assertTrue(all(r['project_id']=='cylindrical-lfp01' and r['source']=='live_cycler_simulator' for r in d['records']))
  self.assertEqual(report(self.rack,self.store,'prismatic-sib')['tests'],[])
  with self.assertRaises(ValueError):report(self.rack,self.store,'bad-project')
 def test_persisted_original_doe_reused_in_reports(self):
  first=canonical(self.store);second=canonical(self.store)
  self.assertEqual(first,second)
  other=ProjectStore(self.store.path)
  try:self.assertEqual(canonical(other),first)
  finally:other.close()
 def test_fault_issue_same_cell_and_resolution_survives_poll(self):
  self.rack.trip(self.rack.cells[7],'Overheat')
  d=report(self.rack,self.store,'cylindrical-lfp01');self.assertEqual(len(d['issues']),1)
  i=d['issues'][0];self.assertEqual(i['doe_id'],'DOE-08')
  api(self.store,'resolve',dict(id=i['id'],resolution='Investigated'))
  d=report(self.rack,self.store,'cylindrical-lfp01');self.assertEqual(d['issues'][0]['status'],'resolved')
  self.assertTrue(d['safety_stop']);self.assertEqual(len(report(self.rack,self.store,'prismatic-lfp01')['issues']),0)
 def test_edit_same_doe_creates_revision_and_locks_after_start(self):
  d=canonical(self.store)[0];payload=dict(id=d['id'],revision=d['revision'],owner='Our team',objective='Design input',bom=d['bom'])
  payload['bom']['cell']['energy_density']=200
  new=update_design(self.rack,self.store,payload)
  self.assertEqual(new['revision'],2)
  current=report(self.rack,self.store,'prismatic-lfp01')
  self.assertEqual(current['does'][0]['bom']['cell']['energy_density'],200)
  self.assertEqual(current['tests'][0]['revision'],2)
  with self.assertRaises(ValueError):update_design(self.rack,self.store,payload)
  self.rack.running=True;self.rack.tick(.5);payload['revision']=2
  with self.assertRaises(ValueError):update_design(self.rack,self.store,payload)
if __name__=='__main__':unittest.main()
