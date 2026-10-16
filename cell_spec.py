"""Versioned cell-design sheets; example templates are not factory specifications."""
import copy
import math
from doe import CATHODES,ANODES,geometry

PROJECTS=[dict(id=f'{form.lower()}-{chem.lower()}',name=f'{form} · {chem}',form_factor=form,
               chemistry='sodium-ion' if chem=='SIB' else 'LFP',code=chem)
          for form in ['PRISMATIC','CYLINDRICAL'] for chem in ['LFP01','SIB']]


def num(label,unit='',default=None,lo=0,hi=100000,role='recorded'):
    return dict(label=label,type='number',unit=unit,default=default,min=lo,max=hi,role=role)


def text(label,default='',role='recorded'):
    return dict(label=label,type='text',unit='',default=default,role=role)


FIELDS={
 'cell':{
  'np_ratio':num('N/P Ratio','',1.1,0.8,2.5,'modeled'),
  'areal_capacity':num('Areal Capacity','mAh/cm²',2.7072,0.01,50,'validation'),
  'nominal_voltage':num('Nominal Voltage','V',3.2,0.1,6,'target'),
  'capacity_033_typical':num('Capacity 0.33C/0.33C · Typical','Ah',2.5,0.1,2000,'modeled'),
  'capacity_033_min':num('Capacity 0.33C/0.33C · Min','Ah',2.4,0.01,2000,'target'),
  'capacity_1c':num('Capacity 1C/1C','Ah',2.3,0.01,2000,'target'),
  'weight':num('Cell Weight · giới hạn','g',55,1,100000,'target'),
  'energy_density':num('Energy Density · target','Wh/kg',150,50,500,'target')},
 'cathode':{
  'active_1':text('Active Material 1','LFP','modeled'),'active_1_pct':num('Active Material 1','wt% dry',94,0,100,'modeled'),
  'additive':text('Additive'),'additive_pct':num('Additive','wt% dry',0,0,100),
  'binder_1':text('Binder Material 1','PVDF'),'binder_1_pct':num('Binder Material 1','wt% dry',2,0,100),
  'binder_2':text('Binder Material 2'),'binder_2_pct':num('Binder Material 2','wt% dry',0,0,100),
  'conductor_1':text('Conductor Material 1','Carbon black'),'conductor_1_pct':num('Conductor Material 1','wt% dry',4,0,100),
  'conductor_2':text('Conductor Material 2'),'conductor_2_pct':num('Conductor Material 2','wt% dry',0,0,100),
  'dispersant':text('Dispersant'),'dispersant_pct':num('Dispersant','wt% dry',0,0,100),
  'solvent':text('Solvent','NMP'), 'foil':text('Cathode foil','Al'),
  'foil_thickness':num('Cathode foil thickness','µm',15,1,100),
  'thickness':num('Electrode Thickness','µm',75,1,1000,'validation'),
  'loading':num('Loading level','mg/cm²',18,3,40,'modeled'),
  'density':num('Density','g/cc',2.4,1,4,'modeled')},
 'anode':{
  'active_1':text('Active Material 1','Graphite','modeled'),'active_1_pct':num('Active Material 1','wt% dry',94,0,100,'modeled'),
  'active_2':text('Active Material 2'),'active_2_pct':num('Active Material 2','wt% dry',0,0,100),
  'active_3':text('Active Material 3'),'active_3_pct':num('Active Material 3','wt% dry',0,0,100),
  'binder_1':text('Binder Material 1','CMC'),'binder_1_pct':num('Binder Material 1','wt% dry',1.5,0,100),
  'binder_2':text('Binder Material 2','SBR'),'binder_2_pct':num('Binder Material 2','wt% dry',1.5,0,100),
  'binder_3':text('Binder Material 3'),'binder_3_pct':num('Binder Material 3','wt% dry',0,0,100),
  'conductor_1':text('Conductor Material 1','Carbon black'),'conductor_1_pct':num('Conductor Material 1','wt% dry',3,0,100),
  'conductor_2':text('Conductor Material 2'),'conductor_2_pct':num('Conductor Material 2','wt% dry',0,0,100),
  'foil':text('Anode foil','Cu'),'foil_thickness':num('Anode foil thickness','µm',10,1,100),
  'thickness':num('Electrode Thickness','µm',64.66,1,1000,'validation'),
  'loading':num('Loading level','mg/cm²',9.0528,1,80,'validation'),
  'density':num('Density','g/cc',1.4,0.3,2.5,'modeled')},
 'assembly':{
  'cathode_layers':num('Cathode layers','layers',20,1,1000),
  'anode_layers':num('Anode layers','layers',21,1,1000),
  'separator':text('Separator','PE/PP'),'separator_thickness':num('Separator thickness','µm',16,1,100),
  'jr_thickness':num('JR thickness','mm',8,0.1,200),
  'packing_ratio':num('Packing ratio','fraction',0.85,0.1,1),
  'electrolyte':text('Electrolyte','LiPF6-EC-EMC','modeled'),
  'electrolyte_amount':num('Electrolyte amount','g/Ah',3,1,8,'modeled'),
  'can_cap':text('CAN/CAP','Steel can / cap'),'can_cap_mass':num('CAN/CAP mass','g',2,0.1,1000)},
 'formation':{'protocol':text('Protocol','Example: CC/CV 0.1C charge → rest → 0.1C discharge')},
}
for _key in ['cathode_layers','anode_layers']:FIELDS['assembly'][_key]['integer']=True


def project(project_id):
    for p in PROJECTS:
        if p['id']==project_id:return p
    raise ValueError('Unknown project')


def template(project_id):
    p=project(project_id)
    bom={group:{key:spec['default'] for key,spec in fields.items()} for group,fields in FIELDS.items()}
    if p['chemistry']=='sodium-ion':
        bom['cathode']['active_1']='NFPP';bom['anode']['active_1']='HardCarbon'
        bom['assembly']['electrolyte']='NaPF6-carbonate';bom['anode']['foil']='Al'
        bom['cell'].update(nominal_voltage=3.0,energy_density=130,weight=80,areal_capacity=1.8612)
        bom['anode'].update(loading=7.77857142857,density=1.3,thickness=59.835164835)
    return bom


def normalize(project_id,bom):
    if not isinstance(bom,dict) or set(bom)-set(FIELDS):raise ValueError('Unknown cell-sheet group')
    result=template(project_id)
    for group,values in bom.items():
        if not isinstance(values,dict) or set(values)-set(FIELDS[group]):raise ValueError('Unknown cell-sheet field')
        for key,value in values.items():
            spec=FIELDS[group][key]
            if spec['type']=='text':
                if not isinstance(value,str) or len(value)>250:raise ValueError('Invalid text: '+key)
                result[group][key]=value.strip()
            else:
                if value is not None and (type(value) not in (float,int) or not math.isfinite(value) or not spec['min']<=value<=spec['max']):raise ValueError('Numeric value outside bounds: '+key)
                if value is not None and spec.get('integer') and int(value)!=value:raise ValueError('Whole layer count required: '+key)
                result[group][key]=value
    return result


def inspect(project_id,bom):
    p=project(project_id);issues=[]
    def issue(code,message,blocking=False):issues.append(dict(code=code,title=message,severity='error' if blocking else 'warning',blocking=blocking))
    totals={group:sum(value or 0 for key,value in bom[group].items() if key.endswith('_pct')) for group in ['cathode','anode']}
    for group in totals:
        if abs(totals[group]-100)>0.1:issue(group+'_total',f'{group}: dry composition total {totals[group]:.2f}% ≠ 100%',True)
        for key,value in bom[group].items():
            if key.endswith('_pct') and value and not bom[group].get(key[:-4]):issue(group+'_'+key,'Missing material name: '+group+'.'+key,True)
    cell=bom['cell'];c=bom['cathode'];a=bom['anode'];assembly=bom['assembly']
    for group,key in [('formation','protocol'),('assembly','separator'),('assembly','can_cap'),('cathode','foil'),('anode','foil')]:
        if not bom[group][key]:issue(group+'_'+key,'Missing recorded information: '+group+'.'+key)
    for key in ['cathode_layers','anode_layers','separator_thickness','jr_thickness','packing_ratio','can_cap_mass']:
        if assembly[key] is None:issue('assembly_'+key,'Missing recorded information: assembly.'+key)
    required=[('cell',key) for key in cell]+[('cathode',k) for k in ['active_1_pct','loading','density']]+[('anode','active_1_pct'),('anode','density'),('assembly','electrolyte_amount')]
    for group,key in required:
        if bom[group][key] is None:issue(group+'_'+key,'Missing value: '+group+'.'+key,True)
    if c['active_1'] not in CATHODES or a['active_1'] not in ANODES:issue('unknown_material','Active material has no response profile; store sheet but cannot simulate.',True)
    if p['chemistry']=='LFP' and (c['active_1']!='LFP' or a['active_1']=='HardCarbon'):issue('chemistry','LFP01 project requires LFP / lithium-ion-compatible anode.',True)
    if p['chemistry']=='sodium-ion' and (c['active_1']!='NFPP' or a['active_1']!='HardCarbon'):issue('chemistry','SIB template currently supports NFPP / HardCarbon only.',True)
    if a['active_2_pct'] or a['active_3_pct']:issue('unsupported_mixture','Anode active-material blends are recorded but not calibrated for this model.',True)
    if cell['capacity_033_min'] and cell['capacity_033_typical'] and cell['capacity_033_min']>cell['capacity_033_typical']:issue('capacity_limits','Minimum 0.33C capacity exceeds typical capacity.',True)
    for group in ['cathode','anode']:
        layer=bom[group]
        if layer['thickness'] and layer['loading'] and layer['density']:
            derived=layer['loading']*10/layer['density']
            if abs(derived-layer['thickness'])/derived>0.1:issue(group+'_thickness',f'{group}: thickness does not match loading/density within 10%; model derives thickness.')
    if a['active_1'] in ANODES and c['active_1'] in CATHODES and a['loading'] and a['active_1_pct'] and c['active_1_pct'] and c['loading'] and cell['np_ratio']:
        ratio=(a['loading']*a['active_1_pct']*ANODES[a['active_1']]['specific_capacity'])/(c['loading']*c['active_1_pct']*CATHODES[c['active_1']]['specific_capacity'])
        if abs(ratio-cell['np_ratio'])/cell['np_ratio']>0.1:issue('np_consistency','Declared N/P differs from coating-composition-derived ratio by >10%.')
        derived_areal=c['loading']*c['active_1_pct']/100*CATHODES[c['active_1']]['specific_capacity']/1000
        if cell['areal_capacity'] and abs(derived_areal-cell['areal_capacity'])/derived_areal>0.1:issue('areal_consistency','Declared areal capacity differs from coating-derived value by >10%.')
    if any(i['blocking'] for i in issues):return dict(issues=issues,totals=totals,simulation_supported=False,baseline=None)
    solid=1/(a['active_1_pct']/100/ANODES[a['active_1']]['solid_density']+(1-a['active_1_pct']/100)/1.8)
    porosity=1-a['density']/solid
    if not 0.15<=porosity<=0.6:issue('anode_porosity','Anode density implies unsupported porosity (must be 15–60%).',True)
    baseline=dict(energy_density_target_wh_kg=cell['energy_density'],capacity_target_ah=cell['capacity_033_typical'],
                  np_ratio=cell['np_ratio'],cathode=c['active_1'],anode=a['active_1'],electrolyte=assembly['electrolyte'],
                  cathode_loading_mg_cm2=c['loading'],cathode_density_g_cm3=c['density'],active_fraction=c['active_1_pct']/100,
                  anode_porosity=porosity,electrolyte_g_ah=assembly['electrolyte_amount'])
    from doe import prepare
    try:geometry(prepare({'baseline':baseline,'vary':{}})[0]['baseline'])
    except ValueError as error:issue('unsupported_geometry',str(error),True)
    return dict(issues=issues,totals=totals,simulation_supported=not any(i['blocking'] for i in issues),baseline=baseline)


def assess(bom,metrics,status):
    if status!='completed' or not metrics:return dict(passed=False,checks={},state='fault')
    c=bom['cell']
    checks=dict(energy_density=metrics['specific_energy_wh_kg']>=c['energy_density'],
                capacity_033=metrics['capacity_033c_ah']>=c['capacity_033_min'],
                capacity_1c=metrics['capacity_1c_ah']>=c['capacity_1c'],
                weight=metrics['cell_mass_g']<=c['weight'],
                nominal_voltage=abs(metrics['nominal_voltage_v']-c['nominal_voltage'])<=0.05*c['nominal_voltage'])
    return dict(passed=all(checks.values()),checks=checks,state='pass' if all(checks.values()) else 'target_miss')


def effective_sheet(bom,p):
    """Record mapped trial overrides; do not invent effects for recorded-only fields."""
    result=copy.deepcopy(bom);c=result['cathode'];a=result['anode'];cell=result['cell']
    old_inactive=100-c['active_1_pct'];new_active=p['active_fraction']*100
    for key in c:
        if key.endswith('_pct') and key!='active_1_pct':c[key]=c[key]*(100-new_active)/old_inactive
    c.update(active_1=p['cathode'],active_1_pct=new_active,loading=p['cathode_loading_mg_cm2'],density=p['cathode_density_g_cm3'])
    c['thickness']=c['loading']*10/c['density']
    areal=c['loading']*p['active_fraction']*CATHODES[p['cathode']]['specific_capacity']/1000
    a['active_1']=p['anode']
    solid=1/(a['active_1_pct']/100/ANODES[p['anode']]['solid_density']+(1-a['active_1_pct']/100)/1.8)
    a['density']=solid*(1-p['anode_porosity'])
    a['loading']=areal*p['np_ratio']*1000/(ANODES[p['anode']]['specific_capacity']*a['active_1_pct']/100)
    a['thickness']=a['loading']*10/a['density']
    cell.update(np_ratio=p['np_ratio'],capacity_033_typical=p['capacity_target_ah'],energy_density=p['energy_density_target_wh_kg'],areal_capacity=areal)
    result['assembly'].update(electrolyte=p['electrolyte'],electrolyte_amount=p['electrolyte_g_ah'])
    return result
