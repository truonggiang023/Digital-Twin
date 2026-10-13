"""Illustrative cycle-aging model, not calibrated or learned from cell data."""
import math

BASE_RATE = 0.00025  # log-capacity loss per EFC at 25 C, 1 C, 100% DoD


def stress_factor(temperature_c, c_rate, dod=1.0):
    return 2 ** ((temperature_c - 25) / 10) * math.sqrt(max(c_rate, 0.1)) * dod ** 0.3


def forecast(nominal_capacity_ah, initial_resistance_ohm, soh, efc,
             temperature_c=25, c_rate=1, dod=0.8, horizon=2000, eol_soh=0.8):
    """Project additional operational cycles; sensitivity bands are not confidence intervals."""
    bounds = [(nominal_capacity_ah, 0.001, 10000), (initial_resistance_ohm, 0.000001, 100),
              (soh, 0.001, 1), (efc, 0, 1e9), (temperature_c, -10, 60),
              (c_rate, 0.1, 5), (dod, 0.05, 1), (eol_soh, 0.5, 0.95)]
    if any(not math.isfinite(v) or not lo <= v <= hi for v, lo, hi in bounds):
        raise ValueError('Scenario outside supported bounds')
    if type(horizon) is not int or not 10 <= horizon <= 10000:
        raise ValueError('Horizon must be an integer between 10 and 10000 cycles')
    rate = BASE_RATE * stress_factor(temperature_c, c_rate, dod) * dod
    remaining = max(0.0, math.log(soh / eol_soh) / rate)
    def point(cycle):
        health = soh * math.exp(-rate * cycle)
        return dict(cycle=cycle, efc=efc + cycle * dod, soh_percent=100 * health,
                    capacity_ah=nominal_capacity_ah * health,
                    resistance_mohm=1000 * initial_resistance_ohm * (1 + 1.5 * (1-health)),
                    optimistic_soh_percent=100 * soh * math.exp(-0.7 * rate * cycle),
                    pessimistic_soh_percent=100 * soh * math.exp(-1.3 * rate * cycle))
    # At most 201 curve points, including both endpoints.
    cycles = sorted({round(i * horizon / 200) for i in range(201)})
    return dict(model='illustrative-exponential-cycle-aging-v1', calibrated=False,
                scenario=dict(temperature_c=temperature_c, c_rate=c_rate, dod=dod,
                              horizon=horizon, eol_soh=eol_soh),
                remaining_cycles=remaining, remaining_cycles_low=remaining/1.3,
                remaining_cycles_high=remaining/0.7,
                eol_within_horizon=remaining <= horizon,
                initial_soh_percent=soh * 100, points=[point(c) for c in cycles])
