"""Bounded, reproducible DOE with explicitly illustrative cell-design responses."""
import hashlib
import itertools
import json
import math
import random
import statistics

MODEL_VERSION='cell-design-doe-v1'
MAX_RUNS=256
CATHODES={
    'LFP':dict(specific_capacity=160,voltage=3.2,solid_density=3.6,aging=0.7),
    'NMC622':dict(specific_capacity=180,voltage=3.65,solid_density=4.7,aging=1.0),
    'NMC811':dict(specific_capacity=200,voltage=3.7,solid_density=4.8,aging=1.3),
    'NFPP':dict(specific_capacity=110,voltage=3.0,solid_density=3.2,aging=1.0),
}
ANODES={
    'Graphite':dict(specific_capacity=350,solid_density=2.2,voltage_penalty=0,aging=1),
    'Si-Graphite':dict(specific_capacity=650,solid_density=2.25,voltage_penalty=0.05,aging=1.7),
    'LTO':dict(specific_capacity=160,solid_density=3.5,voltage_penalty=1.4,aging=0.5),
    'HardCarbon':dict(specific_capacity=280,solid_density=1.6,voltage_penalty=0,aging=1.2),
}
ELECTROLYTES={
    'LiPF6-EC-EMC':dict(conductivity=10,aging=1),
    'LiPF6-FEC':dict(conductivity=8,aging=0.9),
    'LiFSI-ether':dict(conductivity=12,aging=0.85),
    'NaPF6-carbonate':dict(conductivity=8,aging=1.1),
    'NaFSI-ether':dict(conductivity=10,aging=1.0),
}
FACTORS={
    'energy_density_target_wh_kg':dict(label='Energy Density Target · mục tiêu cell',unit='Wh/kg',min=50,max=500,baseline=220,levels=[180,260],role='objective'),
    'cathode_density_g_cm3':dict(label='Mật độ điện cực cathode sau cán',unit='g/cm³',min=1,max=4,baseline=2.7,levels=[2.4,3.0]),
    'capacity_target_ah':dict(label='Capacity Target',unit='Ah',min=0.1,max=2000,baseline=2.5,levels=[2.5,3.0]),
    'np_ratio':dict(label='N/P capacity ratio',unit='',min=0.8,max=2.5,baseline=1.1,levels=[1.05,1.2]),
    'cathode':dict(label='Vật liệu Cathode',unit='',options=list(CATHODES),baseline='NMC622',levels=['LFP','NMC811']),
    'anode':dict(label='Vật liệu Anode',unit='',options=list(ANODES),baseline='Graphite',levels=['Graphite','Si-Graphite']),
    'electrolyte':dict(label='Electrolyte',unit='',options=list(ELECTROLYTES),baseline='LiPF6-EC-EMC',levels=['LiPF6-EC-EMC','LiPF6-FEC']),
    'cathode_loading_mg_cm2':dict(label='Cathode coating loading · tổng chất rắn',unit='mg/cm²',min=3,max=40,baseline=18,levels=[12,24]),
    'active_fraction':dict(label='Tỷ lệ vật liệu hoạt tính cathode',unit='fraction',min=0.8,max=0.99,baseline=0.94,levels=[0.9,0.96]),
    'anode_porosity':dict(label='Độ xốp anode',unit='fraction',min=0.15,max=0.6,baseline=0.3,levels=[0.25,0.4]),
    'electrode_conductivity_s_m':dict(label='Độ dẫn điện hiệu dụng electrode',unit='S/m',min=0.5,max=100,baseline=10,levels=[5,20]),
    'electrolyte_g_ah':dict(label='Lượng điện phân',unit='g/Ah',min=1,max=8,baseline=3,levels=[2,4]),
    'temperature_c':dict(label='Nhiệt độ môi trường',unit='°C',min=10,max=45,baseline=25,levels=[25,35]),
    'c_rate':dict(label='Dòng thử nghiệm',unit='C',min=0.1,max=3,baseline=1,levels=[0.5,1.5]),
}
DEFAULT_VARY=['np_ratio','cathode','electrolyte','cathode_loading_mg_cm2']
METRICS={
    'specific_energy_wh_kg':'Năng lượng riêng (Wh/kg)',
    'specific_energy_final_wh_kg':'Năng lượng riêng cuối thử nghiệm (Wh/kg)',
    'usable_capacity_ah':'Dung lượng khả dụng (Ah)',
    'resistance_mohm':'Nội trở ban đầu (mΩ)',
    'peak_temperature_c':'Nhiệt độ cao nhất (°C)',
    'soh_final_percent':'SOH cuối (%)',
    'cycles_to_80':'Chu kỳ mô phỏng đến SOH 80%',
    'energy_density_margin_wh_kg':'Chênh lệch so với Energy Density Target (Wh/kg)',
}


def schema():
    return dict(model_version=MODEL_VERSION,factors=FACTORS,default_vary=DEFAULT_VARY,
                metrics=METRICS,max_runs=MAX_RUNS,default_cycles=500,
                density_definition='Energy Density Target is a cell-level objective in Wh/kg; cathode bulk density is a separate g/cm³ design input.',
                calibrated=False,data_origin='synthetic_doe',
                assumptions=dict(cathodes=CATHODES,anodes=ANODES,electrolytes=ELECTROLYTES))


def number(value,lo,hi,name,integer=False):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError(f'{name}: expected {lo}–{hi}')
    if integer and type(value) is not int:raise ValueError(f'{name}: expected integer')
    return value


def validate_value(key,value):
    spec=FACTORS[key]
    if 'options' in spec:
        if not isinstance(value,str) or value not in spec['options']:raise ValueError('Unknown material: '+key)
    else:number(value,spec['min'],spec['max'],key)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]


def prepare(config):
    if not isinstance(config,dict) or set(config)-{'method','baseline','vary','cycles','replicates','seed','samples','variation_percent'}:
        raise ValueError('Invalid DOE configuration fields')
    method=config.get('method','factorial')
    if method not in ('factorial','balanced','ofat'):raise ValueError('Unknown DOE method')
    cycles=number(config.get('cycles',500),1,5000,'cycles',True)
    replicates=number(config.get('replicates',1),1,5,'replicates',True)
    seed=number(config.get('seed',42),0,2**31-1,'seed',True)
    samples=number(config.get('samples',24),2,128,'samples',True)
    variation=number(config.get('variation_percent',0),0,5,'variation_percent')
    baseline={k:v['baseline'] for k,v in FACTORS.items()}
    provided=config.get('baseline',{})
    if not isinstance(provided,dict) or set(provided)-set(FACTORS):raise ValueError('Unknown baseline factor')
    baseline.update({k:validate_value(k,v) for k,v in provided.items()})
    vary=config.get('vary',{k:FACTORS[k]['levels'] for k in DEFAULT_VARY})
    if not isinstance(vary,dict) or set(vary)-set(FACTORS):raise ValueError('Unknown varying factor')
    for k,levels in vary.items():
        if FACTORS[k].get('role')=='objective':raise ValueError('Energy Density Target is an objective, not a causal DOE factor; vary physical design inputs')
        if not isinstance(levels,list) or not 2<=len(levels)<=4:raise ValueError(k+': choose 2–4 distinct levels')
        for v in levels:validate_value(k,v)
        if len(set(levels))!=len(levels):raise ValueError('Duplicate levels: '+k)
    clean=dict(method=method,cycles=cycles,replicates=replicates,seed=seed,samples=samples,
               variation_percent=variation,baseline=baseline,vary=vary)
    keys=sorted(vary)
    rng=random.Random(seed)
    if not keys:designs=[baseline.copy()]
    elif method=='factorial':
        count=math.prod(len(vary[k]) for k in keys)
        if count*replicates>MAX_RUNS:raise ValueError(f'{count*replicates} runs exceeds {MAX_RUNS}; reduce factors/levels or choose balanced sampling')
        designs=[dict(baseline,**dict(zip(keys,values))) for values in itertools.product(*(vary[k] for k in keys))]
    elif method=='ofat':
        designs=[baseline.copy()]
        for k in keys:
            designs.extend(dict(baseline,**{k:v}) for v in vary[k] if v!=baseline[k])
    else:
        columns={}
        for k in keys:
            values=[vary[k][i%len(vary[k])] for i in range(samples)];rng.shuffle(values);columns[k]=values
        designs=[dict(baseline,**{k:columns[k][i] for k in keys}) for i in range(samples)]
    unique={digest({k:v for k,v in d.items() if FACTORS[k].get('role')!='objective'}):d for d in designs}
    if len(unique)*replicates>MAX_RUNS:raise ValueError('Run count exceeds limit')
    experiment_id=digest(dict(model=MODEL_VERSION,config=clean))
    rows=[]
    for design_id,design in unique.items():
        for replicate in range(1,replicates+1):
            group=int(design_id[:8],16)%20
            rows.append(dict(run_id=f'{design_id}-{replicate}',design_id=design_id,replicate=replicate,
                             ml_split='test' if group>=17 else 'validation' if group>=14 else 'train',inputs=design.copy()))
    rng.shuffle(rows)
    for i,row in enumerate(rows):row['run_order']=i+1
    return clean,dict(experiment_id=experiment_id,config=clean,runs=rows,run_count=len(rows),
                      unique_designs=len(unique),model_version=MODEL_VERSION,data_origin='synthetic_doe',calibrated=False)


def geometry(p):
    cath=CATHODES[p['cathode']];anode=ANODES[p['anode']]
    sodium=p['cathode']=='NFPP'
    if sodium!=(p['anode']=='HardCarbon') or sodium!=p['electrolyte'].startswith('Na'):
        raise ValueError('Lithium/sodium cathode, anode and electrolyte families must match')
    if p['np_ratio']<1:raise ValueError('N/P < 1: insufficient nominal anode capacity')
    if p['electrolyte']=='LiFSI-ether' and p['cathode']!='LFP':
        raise ValueError('Illustrative ether formulation is not supported with high-voltage NMC')
    # Two-solid mixture, binder/carbon lumped density 1.8 g/cm³.
    solid_density=1/(p['active_fraction']/cath['solid_density']+(1-p['active_fraction'])/1.8)
    porosity=1-p['cathode_density_g_cm3']/solid_density
    if not 0.08<=porosity<=0.65:raise ValueError('Cathode bulk density implies porosity outside 8–65%')
    coating_mass=p['capacity_target_ah']*1000/cath['specific_capacity']/p['active_fraction']
    area=coating_mass/(p['cathode_loading_mg_cm2']/1000)
    thickness=p['cathode_loading_mg_cm2']/1000/p['cathode_density_g_cm3']*10000
    anode_mass=p['np_ratio']*p['capacity_target_ah']*1000/anode['specific_capacity']/0.95
    # Example double-sided collectors: 6 µm Al and 4 µm Cu per coated area.
    collectors=area*(0.0006*2.7+0.0004*8.96)
    mass=coating_mass+anode_mass+collectors+area*0.001+p['electrolyte_g_ah']*p['capacity_target_ah']+2
    return dict(cathode_porosity=porosity,cathode_thickness_um=thickness,electrode_area_cm2=area,cell_mass_g=mass)


def evaluate(p,cycles,rng,variation):
    g=geometry(p);cath=CATHODES[p['cathode']];anode=ANODES[p['anode']];electro=ELECTROLYTES[p['electrolyte']]
    transport=(g['cathode_thickness_um']/65)**1.2*(0.3/g['cathode_porosity'])**1.5
    anode_transport=(0.3/p['anode_porosity'])**1.5
    resistance=0.012*(2.5/p['capacity_target_ah'])*(0.4+0.35*transport+0.15*anode_transport+0.1*10/p['electrode_conductivity_s_m'])*10/electro['conductivity']
    resistance*=max(0.5,1+rng.gauss(0,variation/100))
    voltage=cath['voltage']-anode['voltage_penalty']
    utilization=1/(1+0.035*p['c_rate']*transport)
    capacity=p['capacity_target_ah']*utilization*max(0.5,1+rng.gauss(0,variation/100))
    current=p['capacity_target_ah']*p['c_rate']
    cooling=0.3*(p['capacity_target_ah']/2.5)**(2/3)
    soh=1.0;peak=p['temperature_c'];curve=[dict(cycle=0,soh_percent=100,capacity_ah=capacity)]
    eol=None;stop_reason='';completed=0
    for cycle in range(1,cycles+1):
        effective_r=resistance*(1+1.5*(1-soh))
        temperature=p['temperature_c']+current**2*effective_r/cooling
        peak=max(peak,temperature)
        if temperature>=45:
            stop_reason='Thermal STOP: simulated steady temperature ≥45 °C';break
        penalty=1+2*abs(p['np_ratio']-1.1)+0.15*transport+0.1*max(0,3-p['electrolyte_g_ah'])
        rate=0.00025*2**((temperature-25)/10)*math.sqrt(p['c_rate'])*cath['aging']*anode['aging']*electro['aging']*penalty
        soh*=math.exp(-rate*0.8)
        completed=cycle
        if eol is None and soh<=0.8:eol=cycle
        if cycle%max(1,math.ceil(cycles/100))==0 or cycle==cycles:
            curve.append(dict(cycle=cycle,soh_percent=100*soh,capacity_ah=capacity*soh))
    if curve[-1]['cycle']!=completed:curve.append(dict(cycle=completed,soh_percent=100*soh,capacity_ah=capacity*soh))
    specific_energy=capacity*voltage/(g['cell_mass_g']/1000)
    return dict(**g,usable_capacity_ah=capacity,specific_energy_wh_kg=specific_energy,
                nominal_voltage_v=voltage,capacity_033c_ah=p['capacity_target_ah']/(1+0.035*0.33*transport),
                capacity_1c_ah=p['capacity_target_ah']/(1+0.035*transport),
                areal_capacity_mah_cm2=p['cathode_loading_mg_cm2']*p['active_fraction']*cath['specific_capacity']/1000,
                specific_energy_final_wh_kg=specific_energy*soh,
                energy_density_margin_wh_kg=specific_energy-p['energy_density_target_wh_kg'],
                energy_target_met=specific_energy>=p['energy_density_target_wh_kg'],
                energy_wh=capacity*voltage,resistance_mohm=resistance*1000,peak_temperature_c=peak,
                soh_final_percent=100*soh,capacity_final_ah=capacity*soh,cycles_to_80=eol,
                eol_censored=eol is None,completed_cycles=completed,
                status='stopped' if stop_reason else 'completed',reason=stop_reason,curve=curve)


def analyze(rows,vary):
    effects={}
    for metric in METRICS:
        factors=[]
        for key,levels in vary.items():
            groups=[]
            for level in levels:
                values=[r['metrics'][metric] for r in rows if r['status']=='completed' and r['inputs'][key]==level and r['metrics'][metric] is not None]
                groups.append(dict(level=level,n=len(values),mean=statistics.mean(values) if values else None,
                                   std=statistics.stdev(values) if len(values)>1 else None))
            means=[g['mean'] for g in groups if g['mean'] is not None]
            factors.append(dict(factor=key,levels=groups,effect_range=max(means)-min(means) if len(means)>1 else None))
        effects[metric]=sorted(factors,key=lambda f:-(f['effect_range'] if f['effect_range'] is not None else -1))
    return effects


def run_experiment(config):
    clean,report=prepare(config)
    for row in report['runs']:
        rng=random.Random(int(digest(dict(seed=clean['seed'],run_id=row['run_id'])),16))
        try:
            metrics=evaluate(row['inputs'],clean['cycles'],rng,clean['variation_percent'])
            row.update(status=metrics['status'],reason=metrics['reason'],metrics=metrics)
        except ValueError as error:row.update(status='infeasible',reason=str(error),metrics=None)
    report['effects']=analyze(report['runs'],clean['vary'])
    report['summary']={status:sum(r['status']==status for r in report['runs']) for status in ['completed','stopped','infeasible']}
    report['summary']['energy_target_met']=sum(r['status']=='completed' and r['metrics']['energy_target_met'] for r in report['runs'])
    report['assumptions']=schema()['assumptions']
    report['factor_schema']=FACTORS
    report['metric_labels']=METRICS
    report['analysis_note']='Marginal means of completed runs, not causal inference or statistical significance. Filtering infeasible/stopped runs can unbalance factors. Null cycles_to_80 means EOL was not observed, not zero. Replicates share design_id and ML split.'
    return report
