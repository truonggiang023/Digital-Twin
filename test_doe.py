import unittest
from doe import prepare,run_experiment,analyze


class DOETests(unittest.TestCase):
    def test_default_factorial_balance_and_reproducibility(self):
        a=run_experiment({});b=run_experiment({})
        self.assertEqual(a,b);self.assertEqual(a['run_count'],16)
        self.assertEqual(a['summary']['completed'],16)
        for factor in a['config']['vary']:
            counts=[sum(r['inputs'][factor]==level for r in a['runs']) for level in a['config']['vary'][factor]]
            self.assertEqual(counts,[8,8])
        self.assertTrue(all(r['metrics']['soh_final_percent']<=100 for r in a['runs']))

    def test_objective_changes_margin_not_physics_or_split(self):
        a=run_experiment({'vary':{},'baseline':{'energy_density_target_wh_kg':150}})['runs'][0]
        b=run_experiment({'vary':{},'baseline':{'energy_density_target_wh_kg':400}})['runs'][0]
        self.assertEqual(a['metrics']['specific_energy_wh_kg'],b['metrics']['specific_energy_wh_kg'])
        self.assertTrue(a['metrics']['energy_target_met']);self.assertFalse(b['metrics']['energy_target_met'])
        self.assertEqual(a['design_id'],b['design_id']);self.assertEqual(a['ml_split'],b['ml_split'])

    def test_replicates_stay_in_same_split(self):
        r=run_experiment({'vary':{'np_ratio':[1.05,1.2]},'replicates':3,'variation_percent':1})
        self.assertEqual(r['run_count'],6)
        for design in {x['design_id'] for x in r['runs']}:
            rows=[x for x in r['runs'] if x['design_id']==design]
            self.assertEqual(len({x['ml_split'] for x in rows}),1)
            self.assertGreater(len({x['metrics']['resistance_mohm'] for x in rows}),1)

    def test_invalid_combinations_are_retained_with_reason(self):
        for baseline in [{'np_ratio':0.9},{'cathode':'LFP','cathode_density_g_cm3':4},
                         {'cathode':'NMC811','electrolyte':'LiFSI-ether'}]:
            r=run_experiment({'vary':{},'baseline':baseline})
            self.assertEqual(r['summary']['infeasible'],1)
            self.assertIsNone(r['runs'][0]['metrics']);self.assertTrue(r['runs'][0]['reason'])

    def test_thermal_stop_and_censored_eol(self):
        stopped=run_experiment({'vary':{},'baseline':{'temperature_c':45}})['runs'][0]
        self.assertEqual(stopped['status'],'stopped');self.assertEqual(stopped['metrics']['completed_cycles'],0)
        healthy=run_experiment({'vary':{},'cycles':1})['runs'][0]['metrics']
        self.assertIsNone(healthy['cycles_to_80']);self.assertTrue(healthy['eol_censored'])
        self.assertEqual(healthy['curve'][-1]['cycle'],1)

    def test_bounded_input_validation(self):
        for config in [{'cycles':0},{'cycles':float('nan')},{'seed':True},{'replicates':1.5},
                       {'baseline':{'np_ratio':float('inf')}},{'baseline':{'anode':'unknown'}},
                       {'vary':{'np_ratio':[1.1,1.1]}},{'vary':{'energy_density_target_wh_kg':[150,250]}},
                       {'vary':{'bad':[1,2]}},{'extra':1}]:
            with self.subTest(config=config),self.assertRaises(ValueError):prepare(config)
        many={k:[spec['baseline'],spec['min']] for k,spec in __import__('doe').FACTORS.items() if 'min' in spec and spec.get('role')!='objective' and spec['baseline']!=spec['min']}
        with self.assertRaises(ValueError):prepare({'vary':many,'replicates':5})

    def test_ofat_and_balanced_sampling(self):
        c={'vary':{'np_ratio':[1.05,1.2],'cathode':['LFP','NMC811']}}
        self.assertEqual(prepare(dict(c,method='ofat'))[1]['run_count'],5)
        a=prepare(dict(c,method='balanced',samples=24))[1]
        self.assertLessEqual(a['run_count'],4)
        self.assertEqual(a,prepare(dict(c,method='balanced',samples=24))[1])

    def test_known_main_effect_and_missing_group(self):
        rows=[dict(status='completed',inputs={'np_ratio':level},metrics={key:level*10 for key in __import__('doe').METRICS}) for level in [1,1,2,2]]
        effects=analyze(rows,{'np_ratio':[1,2]})['specific_energy_wh_kg'][0]
        self.assertEqual(effects['effect_range'],10)
        self.assertEqual([x['mean'] for x in effects['levels']],[10,20])

    def test_cli_exports_real_rows_without_losing_status(self):
        import csv,json,tempfile
        from pathlib import Path
        from run_doe import export
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=export({'vary':{'np_ratio':[0.9,1.2]}},root)
            self.assertEqual(json.loads((root/'doe-results.json').read_text(encoding='utf-8')),report)
            with (root/'doe-results.csv').open(encoding='utf-8-sig') as file:rows=list(csv.DictReader(file))
            self.assertEqual({r['status'] for r in rows},{'completed','infeasible'})
            self.assertEqual(len(rows),2)


if __name__=='__main__':unittest.main()
