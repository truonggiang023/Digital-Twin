import unittest
from server import Rack
from live_report import report
class LiveReportTests(unittest.TestCase):
 def test_exact_channel_join_and_reset_session(self):
  r=Rack();d=report(r)
  self.assertEqual(len(d['tests']),12);self.assertEqual(len(d['does']),4)
  self.assertEqual([t['channel'] for t in d['tests']],list(range(1,13)))
  self.assertTrue(all(sum(t['doe_id']==doe['id'] for t in d['tests'])==3 for doe in d['does']))
  self.assertEqual([t['form_factor'] for t in d['tests']],['PRISMATIC']*6+['CYLINDRICAL']*6)
  self.assertEqual([t['project_id'] for t in d['tests']],['prismatic-lfp01']*6+['cylindrical-lfp01']*6)
  old=d['session_id'];r.reset();self.assertNotEqual(report(r)['session_id'],old)
 def test_live_progress_and_stop_match_rack(self):
  r=Rack();r.running=True;r.tick(.5);d=report(r)
  self.assertTrue(all(t['telemetry']['time_s']>0 for t in d['tests']))
  self.assertEqual(d['tests'][0]['telemetry']['soh_percent'],r.cells[0]['soh_percent'])
  r.trip(r.cells[2],'Test fault');d=report(r)
  self.assertTrue(d['safety_stop']);self.assertEqual(d['tests'][2]['target_state'],'fault')
  self.assertTrue(all(t['telemetry']['current_a']==0 for t in d['tests']))
 def test_original_design_has_sixty_fields_and_no_fabricated_ce(self):
  r=Rack();d=report(r)
  self.assertEqual(sum(len(fs) for fs in d['does'][0]['bom'].values()),60)
  self.assertTrue(all(t['ce_percent'] is None for t in d['tests']))
if __name__=='__main__':unittest.main()
