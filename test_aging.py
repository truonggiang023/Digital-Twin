import math
import unittest
from aging import forecast, BASE_RATE
from main import Battery, simulate


class AgingTests(unittest.TestCase):
    def prediction(self, **kwargs):
        return forecast(2.5, 0.08, 1, 0, **kwargs)

    def test_reference_and_eol(self):
        p = self.prediction(dod=1)
        self.assertAlmostEqual(p['remaining_cycles'], -math.log(0.8) / BASE_RATE)
        self.assertAlmostEqual(p['points'][0]['capacity_ah'], 2.5)
        self.assertLess(p['points'][-1]['soh_percent'], 100)
        self.assertGreater(p['points'][-1]['resistance_mohm'], 80)
        self.assertEqual(p['points'][-1]['cycle'], 2000)
        self.assertLessEqual(len(p['points']), 201)

    def test_stress_and_sensitivity(self):
        base = self.prediction()
        self.assertLess(self.prediction(temperature_c=35)['remaining_cycles'], base['remaining_cycles'])
        self.assertLess(self.prediction(c_rate=2)['remaining_cycles'], base['remaining_cycles'])
        self.assertGreater(self.prediction(dod=0.4)['remaining_cycles'], base['remaining_cycles'])
        for p in base['points']:
            self.assertLessEqual(p['pessimistic_soh_percent'], p['soh_percent'])
            self.assertGreaterEqual(p['optimistic_soh_percent'], p['soh_percent'])

    def test_eol_already_reached_and_validation(self):
        self.assertEqual(forecast(2.5, 0.08, 0.7, 100)['remaining_cycles'], 0)
        for kwargs in ({'temperature_c':float('nan')}, {'c_rate':0}, {'dod':1.1},
                       {'horizon':2000.5}, {'horizon':10001}, {'eol_soh':1}):
            with self.assertRaises(ValueError):
                self.prediction(**kwargs)

    def test_live_aging_and_rest(self):
        b = Battery()
        b.advance(1, 3600)
        self.assertAlmostEqual(b.efc, 0.2)
        self.assertLess(b.soh, 1)
        self.assertLess(b.usable_capacity_ah, 2.5)
        self.assertGreater(b.effective_resistance_ohm, 0.08)
        old = b.soh
        b.advance(0, 60)
        self.assertEqual(b.soh, old)

    def test_three_actual_cycles(self):
        b = Battery()
        previous_soh = 100
        seen = set()
        for row in simulate(b, cycles=3, current_a=2):
            seen.add(row['cycle'])
            self.assertLessEqual(row['soh_percent'], previous_soh)
            previous_soh = row['soh_percent']
            self.assertTrue(0 <= row['soc'] <= 1)
            self.assertTrue(3 - 1e-5 <= row['voltage_v'] <= 4.2 + 1e-5)
        self.assertEqual(seen, {1,2,3})
        self.assertLess(b.soh, 1)
        self.assertGreater(b.efc, 2)


if __name__ == '__main__':
    unittest.main()
