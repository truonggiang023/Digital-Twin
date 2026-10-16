import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from cell_spec import PROJECTS,template,inspect,effective_sheet
from project_store import ProjectStore


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.store=ProjectStore(Path(self.directory.name)/'workspace.sqlite3')
    def tearDown(self):self.store.close();self.directory.cleanup()
    def design(self,project='prismatic-lfp01',bom=None):
        return self.store.save_design(dict(project_id=project,name='DOE test',bom=bom or template(project)))
    def wait(self,experiment_id):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            e=self.store.experiment(experiment_id)
            if e['status'] not in ('queued','running'):return e
            time.sleep(.01)
        self.fail('Experiment did not finish')

    def test_four_projects_and_all_sheet_groups(self):
        self.assertEqual(len(PROJECTS),4)
        for p in PROJECTS:
            validation=inspect(p['id'],template(p['id']))
            self.assertTrue(validation['simulation_supported'],validation)
            self.assertEqual(validation['totals'],{'cathode':100,'anode':100})

    def test_design_persistence_revision_and_isolation(self):
        d=self.design();other=ProjectStore(self.store.path)
        try:self.assertEqual(other.get_design(d['id'])['bom'],d['bom'])
        finally:other.close()
        self.assertEqual(len(self.store.dashboard('prismatic-lfp01')['designs']),1)
        self.assertFalse(self.store.dashboard('prismatic-sib')['designs'])
        edited=self.store.save_design(dict(id=d['id'],revision=d['revision'],project_id=d['project_id'],name='v2',bom=d['bom']))
        self.assertEqual(edited['revision'],2)
        with self.assertRaises(ValueError):self.store.save_design(dict(id=d['id'],revision=1,project_id=d['project_id'],name='stale',bom=d['bom']))

    def test_blocking_composition_and_mixture_issues(self):
        bom=template('prismatic-lfp01');bom['cathode']['binder_1_pct']=0
        d=self.design(bom=bom);self.assertFalse(d['validation']['simulation_supported'])
        state=self.store.dashboard(d['project_id']);self.assertGreater(state['counts']['open_issues'],0)
        with self.assertRaises(ValueError):self.store.start({'design_id':d['id']})
        bom=template('prismatic-lfp01');bom['anode'].update(active_2='Si',active_2_pct=4,active_1_pct=90)
        self.assertFalse(inspect('prismatic-lfp01',bom)['simulation_supported'])

    def test_lfp_and_sodium_jobs_with_immutable_sheets(self):
        for p in ['prismatic-lfp01','cylindrical-sib']:
            d=self.design(p);e=self.store.start({'design_id':d['id'],'config':{'vary':{},'cycles':5}})
            finished=self.wait(e['id']);self.assertEqual(finished['status'],'completed')
            self.assertEqual(finished['report']['summary']['completed'],1)
            row=finished['report']['runs'][0]
            self.assertEqual(row['effective_bom']['cathode']['active_1'],d['bom']['cathode']['active_1'])
            self.assertIn('capacity_033c_ah',row['metrics'])
            revised=copy.deepcopy(d['bom']);revised['formation']['protocol']='Updated recorded protocol'
            self.store.save_design(dict(id=d['id'],revision=1,project_id=p,name='edited',bom=revised))
            self.assertNotEqual(self.store.experiment(e['id'])['sheet']['formation'],revised['formation'])

    def test_real_running_count_and_global_admission_limit(self):
        d=self.design();entered=threading.Event();release=threading.Event()
        from project_store import evaluate
        def delayed(*args):entered.set();release.wait(3);return evaluate(*args)
        with patch('project_store.evaluate',side_effect=delayed):
            first=self.store.start({'design_id':d['id'],'config':{'vary':{},'cycles':1}})
            self.assertTrue(entered.wait(2))
            state=self.store.dashboard(d['project_id']);self.assertEqual(state['counts']['running'],1)
            second=self.store.start({'design_id':d['id'],'config':{'vary':{},'cycles':1}})
            try:
                with self.assertRaises(ValueError):self.store.start({'design_id':d['id']})
            finally:release.set()
            self.assertEqual(self.wait(first['id'])['status'],'completed');self.assertEqual(self.wait(second['id'])['status'],'completed')

    def test_targets_faults_and_resolution_do_not_rewrite_data(self):
        d=self.design();e=self.store.start({'design_id':d['id'],'config':{'vary':{'np_ratio':[0.9,1.2]},'cycles':5,'baseline':{'energy_density_target_wh_kg':500}}})
        self.wait(e['id']);state=self.store.dashboard(d['project_id'])
        self.assertEqual(state['counts']['faults'],1);self.assertEqual(state['counts']['target_miss'],1)
        self.assertEqual(state['counts']['target_pass'],0);self.assertEqual(state['counts']['open_issues'],2)
        issue=state['issues'][0];self.store.resolve(issue['id'],{'resolution':'Reviewed and quarantined'})
        self.assertIsNotNone(issue['cell_number']);self.assertTrue(issue['experiment_name'])
        after=self.store.dashboard(d['project_id']);self.assertEqual(after['counts']['open_issues'],1)
        self.assertEqual(after['counts']['faults'],1)

    def test_job_rejects_wrong_project_chemistry(self):
        d=self.design('prismatic-sib')
        with self.assertRaises(ValueError):self.store.start({'design_id':d['id'],'config':{'baseline':{'cathode':'LFP'},'vary':{}}})

    def test_prismatic_capacity_is_not_limited_to_small_demo_cells(self):
        bom=template('prismatic-lfp01')
        bom['cell'].update(capacity_033_typical=280,capacity_033_min=270,capacity_1c=250,weight=6000)
        d=self.design(bom=bom)
        self.assertTrue(d['validation']['simulation_supported'])
        self.assertEqual(d['validation']['baseline']['capacity_target_ah'],280)

    def test_sheet_revalidation_resolves_only_sheet_issues(self):
        bom=template('prismatic-lfp01');bom['formation']['protocol']=''
        d=self.design(bom=bom);self.assertEqual(self.store.dashboard(d['project_id'])['counts']['open_issues'],1)
        self.store.save_design(dict(id=d['id'],revision=1,project_id=d['project_id'],name='fixed',bom=template(d['project_id'])))
        self.assertEqual(self.store.dashboard(d['project_id'])['counts']['open_issues'],0)

    def test_stale_jobs_are_interrupted_not_falsely_running(self):
        d=self.design();e=self.store.start({'design_id':d['id'],'config':{'vary':{},'cycles':1}});self.wait(e['id'])
        with self.store.db() as db:
            db.execute("UPDATE experiments SET status='running',updated=0 WHERE id=?",(e['id'],))
            db.execute("UPDATE samples SET status='running' WHERE experiment_id=?",(e['id'],))
        state=self.store.dashboard(d['project_id']);self.assertEqual(state['counts']['running'],0)
        self.assertEqual(state['counts']['faults'],1);self.assertEqual(state['experiments'][0]['faults'],1)
        self.assertEqual(state['counts']['target_pass'],0)

    def test_effective_recipe_totals_and_density_consistency(self):
        d=self.design();p=dict(d['validation']['baseline'],active_fraction=.9,np_ratio=1.2,cathode_loading_mg_cm2=24)
        result=effective_sheet(d['bom'],p)
        checked=inspect(d['project_id'],result)
        self.assertTrue(checked['simulation_supported'])
        self.assertAlmostEqual(checked['totals']['cathode'],100)
        self.assertFalse(any(i['code']=='np_consistency' for i in checked['issues']))


if __name__=='__main__':unittest.main()
