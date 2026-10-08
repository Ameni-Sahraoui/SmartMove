import csv
import io
import json
from collections import defaultdict
from datetime import date,datetime,timedelta
from pathlib import Path
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import Response
from . import config
from .database import rows,row,scalar,audit,transaction,utcnow
from .security import require,current_user,allowed
from .resources import DEFS,scope

router=APIRouter(prefix='/api')


def artifact(name):
    path=config.ARTIFACTS/f'{name}.json'
    if not path.exists():return None
    return json.loads(path.read_text(encoding='utf-8'))


def period(days):
    days=max(7,min(days,180))
    end=date.fromisoformat(scalar("SELECT value FROM meta WHERE key='as_of'"))
    start=end-timedelta(days=days-1)
    return start.isoformat(),(end+timedelta(days=1)).isoformat(),days,end.isoformat()


def summary(start,end):
    a=row("""SELECT COUNT(*) total_trips,COALESCE(SUM(passenger_count),0) passengers,
COALESCE(SUM(revenue_cents),0)/100.0 revenue,COALESCE(SUM(operating_cost_cents),0)/100.0 cost,
COALESCE(SUM(revenue_cents-operating_cost_cents),0)/100.0 profit,
100.0*SUM(CASE WHEN status='Completed' AND delay_min<=15 THEN 1 ELSE 0 END)/NULLIF(SUM(status='Completed'),0) on_time,
AVG(CASE WHEN status='Completed' THEN delay_min END) avg_delay,
100.0*SUM(passenger_count)/NULLIF(SUM(CASE WHEN status<>'Cancelled' THEN capacity ELSE 0 END),0) occupancy,
100.0*SUM(status='Cancelled')/NULLIF(COUNT(*),0) cancellation
FROM trips WHERE departure_utc>=? AND departure_utc<?""",(start,end))
    a['satisfaction']=scalar('SELECT AVG(score) FROM satisfaction WHERE survey_date>=? AND survey_date<?',(start,end))
    return {k:0 if v is None else v for k,v in a.items()}


def forecast_data(route_id=None,grain='month',horizon=180):
    f=artifact('forecast')
    if not f:return {'available':False,'reason':'Run the analytics pipeline to create forecasts.'}
    def key(dt):
        d=date.fromisoformat(dt)
        return d.strftime('%Y-%m') if grain=='month' else (d-timedelta(days=d.weekday())).isoformat() if grain=='week' else dt
    points=defaultdict(lambda:{'actual':None,'forecast':None,'lower':None,'upper':None})
    bound=date.fromisoformat(f['as_of'])+timedelta(days=horizon)
    for x in f['actual']:
        if route_id and x['route_id']!=route_id:continue
        k=key(x['date']);points[k]['actual']=(points[k]['actual'] or 0)+x['actual']
    for x in f['daily']:
        if route_id and x['route_id']!=route_id:continue
        if date.fromisoformat(x['date'])>bound:continue
        k=key(x['date'])
        for val in ['forecast','lower','upper']:points[k][val]=(points[k][val] or 0)+x[val]
    evaluation=[x for x in f['evaluation'] if not route_id or x['route_id']==route_id]
    return {'available':True,'points':[{'date':k,**v} for k,v in sorted(points.items())], 'as_of':f['as_of'],'grain':grain,'band_note':f['band_note'],'evaluation':evaluation,'selection':f['selection']}


@router.get('/dashboard')
def dashboard(request:Request,days:int=30):
    require(request,'overview')
    start,end,days,asof=period(days);a=summary(start,end);pstart=(date.fromisoformat(start)-timedelta(days=days)).isoformat();b=summary(pstart,start)
    mr=artifact('maintenance');risks=sorted(mr['records'],key=lambda x:-x['probability']) if mr else []
    vehicle_status=rows('SELECT status,COUNT(*) count FROM vehicles GROUP BY status');active=next((x['count'] for x in vehicle_status if x['status']=='Active'),0)
    vtotal=sum(x['count'] for x in vehicle_status)
    risk_count=sum(x['risk_score']>=60 for x in risks)
    specs=[('total_trips','Total Trips','count','bus'),('on_time','On-Time Performance','percent','clock'),('avg_delay','Average Delay','minutes','hourglass'),('occupancy','Occupancy Rate','percent','users'),('profit','Route Profitability','currency','chart'),('active','Active Vehicles','count','bus'),('risk','Maintenance Risk Alerts','count','wrench'),('satisfaction','Customer Satisfaction','rating','star')]
    metrics=[]
    for k,label,unit,icon in specs:
        value=active if k=='active' else risk_count if k=='risk' else a[k]
        previous=b.get(k)
        change=None if previous is None or previous==0 else (value-previous if unit in ['percent','rating'] else (value/previous-1)*100)
        metrics.append({'key':k,'label':label,'value':value,'unit':unit,'icon':icon,'change':change,'change_unit':'pp' if unit=='percent' else 'points' if unit=='rating' else '%','good':change is not None and (change<=0 if k in ['avg_delay','risk'] else change>=0),'note':f'of {vtotal} total' if k=='active' else 'model score ≥ 60 / 100' if k=='risk' else f'vs. prior {days} days'})
    delays=rows("SELECT substr(departure_utc,1,10) date,AVG(delay_min) delay FROM trips WHERE status='Completed' AND departure_utc>=? AND departure_utc<? GROUP BY date ORDER BY date",((date.fromisoformat(asof)-timedelta(days=13)).isoformat(),end))
    perf=rows("""SELECT r.id,r.name,COUNT(*) trips,SUM(t.passenger_count) passengers,SUM(t.revenue_cents)/100.0 revenue,SUM(t.revenue_cents-t.operating_cost_cents)/100.0 profit,
100.0*SUM(t.passenger_count)/NULLIF(SUM(CASE WHEN t.status<>'Cancelled' THEN t.capacity ELSE 0 END),0) occupancy,
100.0*SUM(CASE WHEN t.status='Completed' AND t.delay_min<=15 THEN 1 ELSE 0 END)/NULLIF(SUM(t.status='Completed'),0) on_time
FROM trips t JOIN routes r ON r.id=t.route_id WHERE t.departure_utc>=? AND t.departure_utc<? GROUP BY r.id ORDER BY passengers DESC""",(start,end))
    fleet=rows("""SELECT v.type,COUNT(DISTINCT v.id) vehicles,
100.0*COUNT(DISTINCT CASE WHEN t.status IN ('Completed','In progress') THEN CAST(v.id AS TEXT)||substr(t.departure_utc,1,10) END)/(COUNT(DISTINCT v.id)*?) utilization
FROM vehicles v LEFT JOIN trips t ON t.vehicle_id=v.id AND t.departure_utc>=? AND t.departure_utc<? GROUP BY v.type ORDER BY vehicles DESC""",(days,start,end))
    inc=rows('SELECT i.*,v.code vehicle FROM incidents i JOIN vehicles v ON v.id=i.vehicle_id ORDER BY i.incident_time DESC LIMIT 5')
    service={x['id']:x['last_service'] for x in rows('SELECT id,last_service FROM vehicles')}
    for x in risks:x['last_service']=service.get(x['vehicle_id'])
    suggestions=[]
    f=artifact('forecast')
    if f:
        nextmonth=defaultdict(float)
        for x in f['daily'][:]:
            if x['date']<=(date.fromisoformat(asof)+timedelta(days=30)).isoformat():nextmonth[x['route_id']]+=x['forecast']
        candidate=max(perf,key=lambda x:nextmonth[x['id']]/max(x['passengers'],1))
        delta=(nextmonth[candidate['id']]/max(candidate['passengers'],1)-1)*100
        suggestions.append({'icon':'chart','title':f"Review capacity on {candidate['name']}",'body':f"Next 30-day model demand: {nextmonth[candidate['id']]:,.0f} passengers; {delta:+.1f}% vs this {days}-day view. Check comparable periods and available capacity before scheduling.",'page':'demand','route_id':candidate['id'],'evidence':'Forecast snapshot, not a causal estimate or guaranteed demand.'})
    if risks:
        x=risks[0];suggestions.append({'icon':'wrench','title':f"Review vehicle {x['code']}",'body':f"Model risk {x['risk_score']}/100; {x['issue'].lower()}. Review the model explanation and technical records with an engineer.",'page':'predictive','vehicle_id':x['vehicle_id'],'evidence':mr['explanation_notice']})
    if perf:
        x=min(perf,key=lambda x:x['occupancy'] or 0);suggestions.append({'icon':'users','title':f"Investigate {x['name']} utilization",'body':f"Occupancy is {x['occupancy']:.1f}%. Review departure timing, service commitments and passenger feedback before reducing service.",'page':'routes','route_id':x['id'],'evidence':'Descriptive comparison only; accessibility and contractual obligations are not modelled.'})
    return {'as_of':asof,'dataset_version':config.DATASET_VERSION,'metrics':metrics,'summary':a,'delay_trends':delays,'fleet':fleet,'route_performance':perf,'incidents':inc,'maintenance':risks[:5],'recommendations':suggestions,'forecast':forecast_data(horizon=180),'range':{'from':start,'to':asof,'days':days},'notice':'Fictional network and synthetic operational records. Geography is illustrative; no live GPS or official Canadian statistics.'}


@router.get('/network')
def network(request:Request):
    user=current_user(request)
    if not any(allowed(user,m) for m in ['overview','routes','trips','fleet']):raise HTTPException(403)
    return {'facilities':rows('SELECT * FROM facilities'),'routes':rows('SELECT * FROM routes'),'replay':True,'notice':'Illustrative straight-line service links, not road navigation. Vehicle motion is visual replay, not live GPS.'}


@router.get('/analytics/forecast')
def forecast(request:Request,route_id:int|None=None,grain:str='month',horizon:int=180):
    require(request,'demand')
    if grain not in ['day','week','month']:raise HTTPException(422)
    return forecast_data(route_id,grain,max(7,min(horizon,180)))


@router.get('/analytics/{kind}')
def analytics_data(kind:str,request:Request):
    mapping={'maintenance':('predictive','maintenance'),'delay':('delay','delay'),'models':('models','models'),'quality':('quality','quality'),'etl':('quality','etl')}
    if kind not in mapping:raise HTTPException(404)
    module,name=mapping[kind];require(request,module)
    if kind=='quality':
        from analytics.etl import quality
        return quality()
    data=artifact(name)
    if data is None:raise HTTPException(404,'Analytics snapshot not available. Run the analytics pipeline.')
    return data


@router.get('/experience')
def experience(request:Request,days:int=30):
    require(request,'experience');start,end,_,asof=period(days)
    return {'satisfaction':rows('SELECT score,COUNT(*) count FROM satisfaction WHERE survey_date>=? AND survey_date<? GROUP BY score',(start,end)),
    'categories':rows('SELECT category,COUNT(*) count FROM complaints WHERE created_at>=? AND created_at<? GROUP BY category',(start,end)),
    'wait_relationship':rows("SELECT CASE WHEN t.delay_min<5 THEN '0–5 min' WHEN t.delay_min<15 THEN '5–15 min' WHEN t.delay_min<30 THEN '15–30 min' ELSE '30+ min' END delay_band,AVG(s.score) score,COUNT(*) responses FROM satisfaction s JOIN trips t ON t.id=s.trip_id WHERE s.survey_date>=? AND s.survey_date<? GROUP BY delay_band",(start,end)),
    'cohorts':rows("SELECT c.loyalty_tier cohort,COUNT(DISTINCT r.customer_id) passengers,COUNT(*) reservations,SUM(r.price_cents)/100.0 revenue FROM reservations r JOIN customers c ON c.id=r.customer_id WHERE r.created_at>=? AND r.created_at<? AND r.status<>'Cancelled' GROUP BY c.loyalty_tier",(start,end)),
    'notice':'Satisfaction associations are observational and generated synthetically. Survey nonresponse and route mix can bias comparisons.'}


@router.post('/simulate')
async def simulate(request:Request):
    require(request,'simulation');p=await request.json()
    try:cap=float(p.get('capacity_change',0));staff=float(p.get('staffing_change',0));sched=float(p.get('scheduling_change',0))
    except (ValueError,TypeError):raise HTTPException(422)
    if not all(__import__('math').isfinite(x) and -40<=x<=100 for x in [cap,staff,sched]):raise HTTPException(422,'Changes must be between -40% and +100%.')
    start,end,_,_=period(30);base=summary(start,end)
    demand=base['passengers'];capacity=demand/max(base['occupancy']/100,.001);newcapacity=capacity*(1+cap/100)
    effective_change=min(cap,staff)
    delay=max(0,base['avg_delay']*(1-effective_change/300)*(1-sched/500))
    return {'baseline':{'occupancy':base['occupancy'],'delay':base['avg_delay'],'seats':capacity,'passengers':demand},'scenario':{'occupancy':100*demand/max(newcapacity,1),'delay':delay,'seats':newcapacity,'unserved':max(0,demand-newcapacity)},'assumptions':['Passenger demand is held constant','Seat capacity changes proportionally; staffing is an aggregate availability proxy','Illustrative delay formula: baseline × (1 − min(capacity%, staffing%)/300) × (1 − scheduling%/500)'],'notice':'Scenario arithmetic, not a learned causal effect. No schedules, staffing or vehicle assignments are changed.'}


@router.post('/optimize')
async def optimize(request:Request):
    user=require(request,'simulation');p=await request.json()
    try:drivers=int(p.get('drivers',20))
    except (ValueError,TypeError):raise HTTPException(422)
    if not 1<=drivers<=40:raise HTTPException(422,'Choose 1–40 available drivers for the scenario.')
    rs=rows('SELECT id,name,distance_km,duration_min FROM routes WHERE status=\'Active\'')
    for r in rs:r['demand']=float(scalar("SELECT AVG(passenger_count) FROM trips WHERE route_id=? AND status='Completed'",(r['id'],)) or 0)
    vs=rows("SELECT id,code,capacity FROM vehicles WHERE status='Active' ORDER BY capacity DESC LIMIT 40")
    from analytics.optimize import allocate
    try:result=allocate(rs,vs,drivers)
    except ImportError:result=allocate(rs,vs,drivers,use_milp=False)
    with transaction() as con:audit(con,user,'simulate_optimization','simulation',after={'drivers':drivers,'method':result['method']},request=request)
    return result


@router.get('/exports/{dataset}')
def export(request:Request,dataset:str):
    user=current_user(request)
    if dataset in DEFS:
        if not allowed(user,dataset,'export'):raise HTTPException(403)
        w,p=scope(user,dataset)
        data=rows(f"SELECT t.* FROM {DEFS[dataset]['table']} t WHERE {w} LIMIT 50000",p)
        out=io.StringIO();writer=csv.writer(out)
        if data:
            writer.writerow(data[0].keys())
            for x in data:
                writer.writerow([("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for v in x.values()])
        with transaction() as con:audit(con,user,'export',dataset,after={'rows':len(data)},request=request)
        return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="smartmove_{dataset}.csv"'})
    require(request,'quality','export')
    allowed_files={p.stem:p for p in config.EXPORTS.glob('*.csv')}
    if dataset not in allowed_files:raise HTTPException(404)
    source=allowed_files[dataset]
    out=io.StringIO();writer=csv.writer(out)
    with source.open(encoding='utf-8-sig',newline='') as f:
        for record in csv.reader(f):writer.writerow(["'"+v if v.startswith(('=','+','@','\t','\r')) else v for v in record])
    with transaction() as con:audit(con,user,'export','warehouse',dataset,request=request)
    return Response('\ufeff'+out.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{source.name}"'})
