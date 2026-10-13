import unittest
from live_features import EarlyDischargeWindow


class LiveFeatureTests(unittest.TestCase):
    def sample(self,w,t,cycle=1,**overrides):
        data=dict(cycle=cycle,stage='discharge',time_s=t,voltage_v=4-t/10000,
                  current_a=-2,temperature_c=26,ambient_temperature_c=25,stage_start_s=0)
        data.update(overrides)
        return w.add(**data)

    def test_waits_for_full_window_and_excludes_future(self):
        w=EarlyDischargeWindow()
        for t in range(1,600):self.assertIsNone(self.sample(w,t))
        features=self.sample(w,600)
        self.assertEqual(features['current_mean'],2)
        self.assertAlmostEqual(features['voltage_mean'],4-300.5/10000)
        self.assertEqual(w.count,600)
        self.assertIsNone(self.sample(w,601))
        self.assertEqual(w.count,600)
        self.assertNotIn('capacity_ah',features)

    def test_bad_timestamps_and_cell_isolation(self):
        a,b=EarlyDischargeWindow(),EarlyDischargeWindow()
        self.sample(a,1)
        with self.assertRaises(ValueError):self.sample(a,1)
        with self.assertRaises(ValueError):self.sample(a,2,voltage_v=float('nan'))
        self.assertEqual(b.count,0)
        self.assertIsNone(self.sample(a,3,stage='charge'))
        self.assertEqual(a.count,1)

    def test_new_cycle_resets_window(self):
        w=EarlyDischargeWindow()
        self.sample(w,1)
        self.sample(w,2,cycle=2)
        self.assertEqual(w.cycle,2)
        self.assertEqual(w.count,1)

    def test_live_rack_updates_all_channels_then_reset(self):
        from server import Rack
        rack=Rack();rack.running=True;rack.speed=300
        for _ in range(3000):
            if not rack.running:break
            rack.tick(.5)
        for cell in rack.cells:
            prediction=cell['live_ml']
            self.assertEqual(prediction['feature_cycle'],3)
            self.assertEqual(prediction['sample_count'],600)
            self.assertGreater(prediction['remaining_cycles'],0)
            self.assertTrue(prediction['experimental'])
            self.assertFalse(prediction['valid_for_hardware'])
            self.assertNotIn('capacity_ah',prediction['features'])
            self.assertEqual([p['cycle'] for p in cell['live_ml_history']],[1,2,3])
            self.assertEqual(cell['live_ml_history'][-1]['remaining_cycles'],prediction['remaining_cycles'])
        rack.reset()
        self.assertTrue(all(c['live_ml']['remaining_cycles'] is None for c in rack.cells))
        self.assertTrue(all(not c['live_ml_history'] for c in rack.cells))

    def test_fault_does_not_publish_unsafe_prediction(self):
        from server import Rack
        rack=Rack();rack.running=True;rack.pending_fault={'cell':1,'kind':'overvoltage'}
        rack.tick(.1)
        self.assertTrue(rack.safety_stop)
        self.assertEqual(rack.live_windows[0].count,0)
        self.assertIsNone(rack.cells[0]['live_ml']['remaining_cycles'])


if __name__=='__main__':unittest.main()
