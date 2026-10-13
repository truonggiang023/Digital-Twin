"""Accumulate per-channel early-discharge features without capacity labels."""
import math


class EarlyDischargeWindow:
    def __init__(self, window_s=600):
        self.window_s=window_s
        self.cycle=None
        self.start_s=None
        self.last_time_s=None
        self.count=0
        self.means={name:0.0 for name in ('voltage','temperature','current')}
        self.voltage_m2=0.0
        self.voltage_end=None
        self.ambient=None
        self.ready=False
        self.error=None

    def add(self, *, cycle, stage, time_s, voltage_v, current_a, temperature_c,
            ambient_temperature_c, stage_start_s):
        if stage!='discharge':
            return None
        if type(cycle) is not int or cycle<1:
            raise ValueError('Invalid cycle number')
        values=(time_s,voltage_v,current_a,temperature_c,ambient_temperature_c,stage_start_s)
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValueError('Invalid/nonfinite telemetry')
        if self.cycle!=cycle:
            window=self.window_s
            self.__init__(window)
            self.cycle=cycle
            self.start_s=stage_start_s
        if stage_start_s!=self.start_s or time_s<stage_start_s:
            raise ValueError('Inconsistent discharge start timestamp')
        if self.last_time_s is not None and time_s<=self.last_time_s:
            raise ValueError('Duplicate or out-of-order telemetry')
        self.last_time_s=time_s
        if self.ready:
            return None
        elapsed=time_s-self.start_s
        if elapsed<=self.window_s:
            self.count+=1
            for name,value in [('voltage',voltage_v),('temperature',temperature_c),('current',abs(current_a))]:
                delta=value-self.means[name]
                self.means[name]+=delta/self.count
                if name=='voltage':self.voltage_m2+=delta*(value-self.means[name])
            self.voltage_end=voltage_v
            self.ambient=ambient_temperature_c
        if elapsed>=self.window_s:
            if self.count<10:
                self.error='Insufficient samples in the 600-second window'
                return None
            self.ready=True
            return dict(cycle=cycle,voltage_mean=self.means['voltage'],
                        voltage_std=math.sqrt(max(0,self.voltage_m2)/(self.count-1)),
                        voltage_end=self.voltage_end,temperature_mean=self.means['temperature'],
                        current_mean=self.means['current'],ambient_temperature=self.ambient)
        return None
