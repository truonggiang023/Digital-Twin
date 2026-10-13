"""Single-channel battery cycler simulator; positive current means charging."""

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from aging import BASE_RATE, stress_factor


@dataclass
class Battery:
    capacity_ah: float = 2.5
    resistance_ohm: float = 0.08
    soc: float = 0.2
    temperature_c: float = 25.0
    ambient_c: float = 25.0
    efc: float = 0.0
    aging_damage: float = 0.0

    @property
    def soh(self):
        return math.exp(-self.aging_damage)

    @property
    def usable_capacity_ah(self):
        return self.capacity_ah * self.soh

    @property
    def effective_resistance_ohm(self):
        return self.resistance_ohm * (1 + 1.5 * (1 - self.soh))

    def health(self):
        return dict(soh_percent=100*self.soh, capacity_ah=self.usable_capacity_ah,
                    resistance_mohm=1000*self.effective_resistance_ohm, efc=self.efc)

    @property
    def ocv(self):
        # Illustrative linear OCV curve, not a calibrated cell chemistry.
        return 3.0 + 1.2 * self.soc

    def advance(self, current_a, dt_s):
        self.soc = min(1.0, max(0.0, self.soc + current_a * dt_s / (3600 * self.usable_capacity_ah)))
        # Lumped thermal model: heat capacity 50 J/K, cooling 0.3 W/K.
        decay = math.exp(-0.3 * dt_s / 50.0)
        equilibrium = self.ambient_c + current_a**2 * self.effective_resistance_ohm / 0.3
        self.temperature_c = equilibrium + (self.temperature_c - equilibrium) * decay
        # EFC counts charge + discharge throughput / (2 * nominal capacity).
        delta_efc = abs(current_a) * dt_s / (7200 * self.capacity_ah)
        self.efc += delta_efc
        self.aging_damage += BASE_RATE * delta_efc * stress_factor(
            self.temperature_c, abs(current_a) / self.capacity_ah)
        return self.ocv + current_a * self.effective_resistance_ohm


def simulate(battery, cycles=1, current_a=1.0, dt_s=1.0, rest_s=60.0,
             max_temperature_c=45.0):
    """Yield endpoint measurements; raise if a safety limit stops the run."""
    if battery.temperature_c >= max_temperature_c:
        raise RuntimeError("Temperature limit reached; simulation stopped")
    elapsed = 0.0
    for cycle in range(1, cycles + 1):
        for stage in ("charge", "rest_after_charge", "discharge", "rest_after_discharge"):
            stage_time = 0.0
            transferred_ah = 0.0
            # Allow ample time for CV taper, but never run indefinitely.
            timeout = 10 * battery.capacity_ah / current_a * 3600
            while True:
                if stage.startswith("rest"):
                    if stage_time >= rest_s:
                        break
                    step = min(dt_s, rest_s - stage_time)
                    current = 0.0
                    mode = "REST"
                elif stage == "charge":
                    # Implicit endpoint CV current keeps terminal voltage <= 4.2 V.
                    cv_current = max(0.0, (4.2 - battery.ocv) /
                                     (battery.effective_resistance_ohm + 1.2 * dt_s / (3600 * battery.usable_capacity_ah)))
                    current = min(current_a, cv_current)
                    if current <= 0.05 * current_a:
                        break
                    mode = "CC" if current == current_a else "CV"
                    step = dt_s
                else:
                    available = (battery.ocv - 3.0) / (
                        battery.effective_resistance_ohm + 1.2 * dt_s / (3600 * battery.usable_capacity_ah))
                    if available <= 0:
                        break
                    current = -current_a
                    # Shorten final discharge step to land on the 3.0 V cutoff.
                    step = min(dt_s, max(0.0, (battery.ocv - current_a * battery.effective_resistance_ohm - 3.0)
                                          * 3600 * battery.usable_capacity_ah / (1.2 * current_a)))
                    if step < 1e-8:
                        break
                    mode = "CC"
                voltage = battery.advance(current, step)
                elapsed += step
                stage_time += step
                transferred_ah += abs(current) * step / 3600
                yield {"time_s": elapsed, "cycle": cycle, "stage": stage, "mode": mode,
                       "voltage_v": voltage, "current_a": current, "soc": battery.soc,
                       "temperature_c": battery.temperature_c, "stage_capacity_ah": transferred_ah,
                       **battery.health()}
                if battery.temperature_c >= max_temperature_c:
                    raise RuntimeError("Temperature limit reached; simulation stopped")
                if not stage.startswith("rest") and stage_time >= timeout:
                    raise RuntimeError(f"Stage timeout: {stage}")


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--capacity-ah", type=positive, default=2.5)
    parser.add_argument("--current-a", type=positive, default=1.0)
    parser.add_argument("--dt-s", type=positive, default=1.0)
    parser.add_argument("--rest-s", type=positive, default=60.0)
    parser.add_argument("--initial-soc", type=float, default=0.2)
    parser.add_argument("--output", type=Path, default=Path("cycler.csv"))
    args = parser.parse_args()
    if args.cycles < 1 or not math.isfinite(args.initial_soc) or not 0 <= args.initial_soc <= 1:
        parser.error("cycles must be >= 1 and initial SOC must be between 0 and 1")
    battery = Battery(capacity_ah=args.capacity_ah, soc=args.initial_soc)
    fields = ["time_s", "cycle", "stage", "mode", "voltage_v", "current_a", "soc",
              "temperature_c", "stage_capacity_ah", "soh_percent", "capacity_ah",
              "resistance_mohm", "efc"]
    count = 0
    try:
        with args.output.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in simulate(battery, args.cycles, args.current_a, args.dt_s, args.rest_s):
                writer.writerow(row)
                count += 1
    except (RuntimeError, OSError) as error:
        parser.exit(1, f"Stopped: {error}\n")
    print(f"Completed {args.cycles} cycle(s), {count} samples. CSV: {args.output}")


if __name__ == "__main__":
    main()
