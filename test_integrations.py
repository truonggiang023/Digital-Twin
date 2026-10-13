import json
import unittest
from unittest.mock import patch
from batterylake import BatteryLake, BatteryLakeError
from ml_inference import predict, model
from server import Rack


class IntegrationTests(unittest.TestCase):
    def test_metadata_filters_and_no_fake_measurements(self):
        lake=BatteryLake();lake.cache['index.json']={'schema_version':'2.0.0','datasets':[
            dict(dataset_id='dataset_01',dataset_name='NASA',cathode_chemistries=['LCO'],supported_tasks=['SOH','RUL']),
            dict(dataset_id='dataset_03',dataset_name='Stanford',cathode_chemistries=['LFP'],supported_tasks=['SOH'])]}
        result=lake.catalog(chemistry='LCO',task='RUL')
        self.assertEqual(result['matched'],1);self.assertFalse(result['measurement_data_loaded'])
        self.assertEqual(lake.catalog(search='no match')['matched'],0)
        for invalid in ['../dataset_01','dataset_99','dataset_001']:
            with self.assertRaises(ValueError):lake.dataset(invalid)

    def test_metadata_failure_is_reported(self):
        with patch('batterylake.urllib.request.urlopen',side_effect=OSError('offline')):
            with self.assertRaises(BatteryLakeError):BatteryLake().catalog()

    def test_exported_model_matches_saved_test_predictions(self):
        from pathlib import Path
        replay=json.loads((Path(__file__).parent/'results/ml-results.json').read_text(encoding='utf-8'))['replay']
        self.assertNotIn('B0018',model()['training_cells'])
        for row in replay:
            result=predict(row['features'])
            self.assertAlmostEqual(result['soh_percent'],row['predicted_soh'])
            self.assertAlmostEqual(result['remaining_cycles'],row['predicted_rul'])
        with self.assertRaises(ValueError):predict({'Capacity':1})
        invalid=replay[0]['features'].copy();invalid['cycle']=float('nan')
        with self.assertRaises(ValueError):predict(invalid)

    def test_all_faults_stop_entire_rack_and_latch(self):
        for kind in ['overheat','overvoltage','overcurrent','capacity_drop']:
            with self.subTest(kind=kind):
                rack=Rack();rack.running=True;rack.pending_fault={'cell':7,'kind':kind};rack.tick(.1)
                self.assertTrue(rack.safety_stop);self.assertFalse(rack.running)
                self.assertEqual(rack.alarms[0]['cell'],7)
                self.assertTrue(all(c['current_a']==0 for c in rack.cells))
                before=rack.cells[0]['time_s'];rack.tick(.5)
                self.assertEqual(before,rack.cells[0]['time_s'])
                rack.reset();self.assertFalse(rack.safety_stop);self.assertFalse(rack.alarms)

    def test_uninjected_thermal_fault_stops(self):
        rack=Rack();rack.batteries[3].temperature_c=46;rack.running=True;rack.tick(.1)
        self.assertTrue(rack.safety_stop);self.assertEqual(rack.alarms[0]['cell'],4)

    def test_normal_three_cycle_run(self):
        rack=Rack();rack.running=True;rack.speed=300
        for _ in range(3000):
            if not rack.running:break
            rack.tick(.5)
        self.assertFalse(rack.safety_stop)
        self.assertTrue(all(c['status']=='complete' for c in rack.cells))


if __name__=='__main__':unittest.main()
