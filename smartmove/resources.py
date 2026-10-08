import re
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from .database import audit, row, rows, scalar, transaction, utcnow
from .security import allowed, current_user, require, HASHER, password_ok, issue_account_token, ROLES

router=APIRouter(prefix="/api")
PROVINCES=["Ontario","Quebec","Alberta","British Columbia","Manitoba","Saskatchewan"]


def field(label, kind="text", required=True, **kwargs):
    return {"label":label,"type":kind,"required":required,**kwargs}


DEFS={
 "fleet":{"table":"vehicles","title":"Fleet & vehicles","fields":{
  "code":field("Vehicle ID"),"type":field("Type","select",options=["Coach","Transit Bus","Minibus","Paratransit"]),"capacity":field("Seat capacity","number",minimum=1,maximum=100),"facility_id":field("Home terminal","reference",source="facilities"),"status":field("Status","select",options=["Active","Maintenance","Standby"]),"odometer_km":field("Odometer (km)","number",minimum=0,maximum=3000000),"energy":field("Powertrain","select",options=["Diesel","Electric","Hybrid"]),"last_service":field("Last service","date")}},
 "routes":{"table":"routes","title":"Routes","fields":{
  "name":field("Route name"),"origin_id":field("Origin","reference",source="facilities"),"destination_id":field("Destination","reference",source="facilities"),"distance_km":field("Distance (km)","number",minimum=1,maximum=6000),"duration_min":field("Scheduled duration (min)","number",minimum=10,maximum=1440),"fare_cents":field("Fare (CAD cents)","number",minimum=0,maximum=200000),"status":field("Status","select",options=["Active","Paused","Planned"])}},
 "facilities":{"table":"facilities","title":"Stations & facilities","fields":{
  "name":field("Facility name"),"city":field("City"),"province":field("Province","select",options=PROVINCES),"latitude":field("Latitude","number",minimum=-90,maximum=90),"longitude":field("Longitude","number",minimum=-180,maximum=180),"kind":field("Type","select",options=["Hub","Terminal"]),"active":field("Active","select",options=[1,0])}},
 "employees":{"table":"employees","title":"Employees & drivers","fields":{
  "code":field("Employee code"),"name":field("Name"),"job":field("Job","select",options=["Driver","Engineer","Manager","Analyst"]),"facility_id":field("Facility","reference",source="facilities"),"active":field("Active","select",options=[1,0])}},
 "trips":{"table":"trips","title":"Trips & dispatch","fields":{
  "route_id":field("Route","reference",source="routes"),"vehicle_id":field("Vehicle","reference",source="fleet"),"driver_id":field("Driver","reference",source="employees"),"departure_utc":field("Departure (UTC)","datetime-local"),"status":field("Status","select",options=["Scheduled","In progress","Completed","Cancelled"])}},
 "reservations":{"table":"reservations","title":"Reservations & tickets","fields":{
  "trip_id":field("Trip ID","number",minimum=1,maximum=9999999),"customer_id":field("Customer ID","number",minimum=1,maximum=9999999),"seats":field("Seats","number",minimum=1,maximum=8)}},
 "maintenance":{"table":"maintenance","title":"Maintenance work orders","fields":{
  "vehicle_id":field("Vehicle","reference",source="fleet"),"engineer_id":field("Engineer","reference",False,source="employees"),"opened_at":field("Opened","date"),"completed_at":field("Completed","date",False),"category":field("Category","select",options=["Preventive","Brakes","Battery","Engine","Tires","Other"]),"status":field("Status","select",options=["Open","In progress","Completed"]),"cost_cents":field("Cost (CAD cents)","number",minimum=0,maximum=50000000),"summary":field("Work summary","textarea")}},
 "parts":{"table":"parts","title":"Spare-parts inventory","fields":{
  "name":field("Part name"),"quantity":field("Units in stock","number",minimum=0,maximum=100000),"unit_cost_cents":field("Unit cost (CAD cents)","number",minimum=0,maximum=5000000)}},
 "incidents":{"table":"incidents","title":"Operational incidents","fields":{
  "trip_id":field("Trip ID","number",False,minimum=1,maximum=9999999),"vehicle_id":field("Vehicle","reference",source="fleet"),"incident_time":field("Reported at (UTC)","datetime-local"),"location":field("Location"),"type":field("Incident type","select",options=["Road construction","Heavy congestion","Vehicle breakdown","Severe weather","Service disruption","Accident","Delay"]),"severity":field("Impact","select",options=["Low","Medium","High"]),"status":field("Status","select",options=["Active","Ongoing","Resolved"]),"description":field("Description","textarea")}},
 "complaints":{"table":"complaints","title":"Customer complaints","fields":{
  "customer_id":field("Customer ID","number",minimum=1,maximum=9999999),"trip_id":field("Trip ID","number",False,minimum=1,maximum=9999999),"category":field("Category","select",options=["Delay","Accessibility","Communication","Cleanliness","Ticketing"]),"summary":field("Feedback","textarea"),"status":field("Status","select",options=["Open","Investigating","Resolved"])}},
 "documents":{"table":"documents","title":"Documents & procedures","fields":{
  "title":field("Document title"),"category":field("Category"),"body":field("Document text","textarea")}},
 "payments":{"table":"payments","title":"Simulated payments","fields":{}},
}


def validate(definition, payload, partial=False):
    fields=definition["fields"]
    unknown=set(payload)-set(fields)
    if unknown:
        raise HTTPException(422,f"Unknown or protected fields: {', '.join(sorted(unknown))}")
    out={}
    for key, f in fields.items():
        if key not in payload and partial: continue
        value=payload.get(key)
        if value in ("",None):
            if f["required"]: raise HTTPException(422,f"{f['label']} is required.")
            out[key]=None;continue
        if f["type"] in ["number","reference"]:
            try: value=float(value)
            except (ValueError,TypeError): raise HTTPException(422,f"{f['label']} must be numeric.")
            if not __import__('math').isfinite(value) or value<f.get("minimum",1) or value>f.get("maximum",100000000):
                raise HTTPException(422,f"{f['label']} is outside the permitted range.")
            if key not in ["latitude","longitude","distance_km","odometer_km"]:
                if value!=int(value): raise HTTPException(422,f"{f['label']} must be a whole number.")
                value=int(value)
        elif f["type"]=="select":
            if str(value) not in [str(v) for v in f["options"]]: raise HTTPException(422,f"Invalid {f['label']}.")
            if isinstance(f["options"][0],int): value=int(value)
        else:
            if not isinstance(value,str): raise HTTPException(422,f"Invalid {f['label']}.")
            value=value.strip()
            if len(value)>(4000 if f["type"]=="textarea" else 160): raise HTTPException(422,f"{f['label']} is too long.")
            if f["type"] in ["date","datetime-local"]:
                try: dt=datetime.fromisoformat(value.replace('Z','+00:00'))
                except ValueError: raise HTTPException(422,f"Invalid date: {f['label']}.")
                value=dt.date().isoformat() if f["type"]=="date" else dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        out[key]=value
    return out


def scope(user, resource, alias="t"):
    role=user["role"]
    if role=="Driver":
        if resource=="trips": return f"{alias}.driver_id=?",[user["employee_id"] or -1]
        if resource=="incidents": return f"{alias}.trip_id IN (SELECT id FROM trips WHERE driver_id=?)",[user["employee_id"] or -1]
    if role=="Customer":
        if resource in ["reservations","complaints"]: return f"{alias}.customer_id=?",[user["customer_id"] or -1]
        if resource=="payments": return f"{alias}.reservation_id IN (SELECT id FROM reservations WHERE customer_id=?)",[user["customer_id"] or -1]
        if resource=="trips": return f"{alias}.status='Scheduled'",[]
    return "1=1",[]


@router.get("/resources")
def resources(request:Request):
    user=current_user(request)
    return [{"key":m,"title":d["title"],"fields":d["fields"],"actions":[a for a in ["view","create","modify","delete","export"] if allowed(user,m,a)]} for m,d in DEFS.items() if allowed(user,m)]


@router.get("/lookups/{resource}")
def lookup(resource:str,request:Request):
    user=current_user(request)
    if resource not in ["facilities","routes","fleet","employees"]: raise HTTPException(404)
    if user['role']=="Customer" and resource not in ["routes","facilities"]: raise HTTPException(403)
    if user['role']=="Driver" and resource in ['fleet','employees']:
        if resource=='employees': return rows("SELECT id,name AS label FROM employees WHERE id=?",(user['employee_id'],))
        return rows("SELECT DISTINCT v.id,v.code AS label FROM vehicles v JOIN trips t ON t.vehicle_id=v.id WHERE t.driver_id=?",(user['employee_id'],))
    if not allowed(user,resource) and not any(allowed(user,m,"create") for m in ["trips","maintenance","incidents"]): raise HTTPException(403)
    d=DEFS[resource]; label='code' if resource=='fleet' else 'name'
    return rows(f"SELECT id,{label} AS label FROM {d['table']} ORDER BY id LIMIT 500")


@router.get("/resources/{resource}")
def list_resource(resource:str,request:Request,page:int=1,q:str="",status:str="",limit:int=25,route_id:int|None=None):
    if resource not in DEFS: raise HTTPException(404)
    user=require(request,resource)
    limit=max(1,min(limit,100)); page=max(1,page)
    d=DEFS[resource]; table=d['table']; where,params=scope(user,resource)
    if q:
        if len(q)>120: raise HTTPException(422,"Search text is too long.")
        columns=[k for k,v in d['fields'].items() if v['type'] in ['text','textarea']]
        cols=["CAST(t.id AS TEXT)"]+[f"t.{c}" for c in columns]
        where+=" AND ("+" OR ".join(c+" LIKE ? ESCAPE '\\'" for c in cols)+")"
        term=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        params += ['%'+term+'%']*len(cols)
    if status and 'status' in d['fields']:
        where+=' AND t.status=?';params.append(status)
    if resource=='trips' and route_id:
        where+=' AND t.route_id=?';params.append(route_id)
    count=scalar(f"SELECT COUNT(*) FROM {table} t WHERE {where}",params)
    order="t.departure_utc DESC" if resource=='trips' else 't.id DESC'
    data=rows(f"SELECT t.* FROM {table} t WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",params+[limit,(page-1)*limit])
    if resource=='trips':
        route_names={r['id']:r['name'] for r in rows('SELECT id,name FROM routes')}
        vehicle_names={r['id']:r['code'] for r in rows('SELECT id,code FROM vehicles')}
        for x in data:
            x['route']=route_names[x['route_id']]; x['vehicle']=vehicle_names[x['vehicle_id']]
            if user['role']=='Customer':
                for k in ['driver_id','operating_cost_cents','fuel_liters','weather_index','congestion_index','revenue_cents','delay_min']:
                    x.pop(k,None)
    if resource=='reservations':
        for x in data:
            x['ticket']=scalar('SELECT reference FROM tickets WHERE reservation_id=?',(x['id'],))
    return {"items":data,"total":count,"page":page,"limit":limit}


def assert_owned(con,user,resource,identifier):
    w,p=scope(user,resource)
    data=row(f"SELECT t.* FROM {DEFS[resource]['table']} t WHERE t.id=? AND {w}",[identifier]+p,con)
    if not data: raise HTTPException(404,"Record not found in your authorized workspace.")
    return data


def cross_validate(con,resource,data,user):
    if resource=='routes' and data.get('origin_id')==data.get('destination_id'):
        raise HTTPException(422,"Origin and destination must differ.")
    if resource=='maintenance':
        if data.get('completed_at') and data['completed_at']<data['opened_at']: raise HTTPException(422,"Completion cannot precede opening.")
        if data.get('engineer_id') and not row("SELECT id FROM employees WHERE id=? AND job='Engineer' AND active=1",(data['engineer_id'],),con): raise HTTPException(422,"Select an active engineer.")
    if resource=='incidents':
        if data.get('trip_id'):
            trip=row('SELECT * FROM trips WHERE id=?',(data['trip_id'],),con)
            if not trip or trip['vehicle_id']!=data['vehicle_id']: raise HTTPException(422,"Vehicle must match the selected trip.")
            if user['role']=='Driver' and trip['driver_id']!=user['employee_id']: raise HTTPException(403,"Drivers can only report assigned trips.")
        elif user['role']=='Driver': raise HTTPException(422,"A driver report requires an assigned trip.")
    if resource=='complaints' and user['role']=='Customer':
        if data['customer_id']!=user['customer_id']: raise HTTPException(403)
        if data.get('trip_id') and not row("SELECT id FROM reservations WHERE customer_id=? AND trip_id=?",(user['customer_id'],data['trip_id']),con): raise HTTPException(403,"Feedback must refer to your own reservation.")


def make_trip(con,data,existing=None):
    rt=row("SELECT * FROM routes WHERE id=? AND status='Active'",(data['route_id'],),con)
    v=row("SELECT * FROM vehicles WHERE id=? AND status='Active'",(data['vehicle_id'],),con)
    driver=row("SELECT * FROM employees WHERE id=? AND job='Driver' AND active=1",(data['driver_id'],),con)
    if not rt or not v or not driver: raise HTTPException(422,"Choose an active route, vehicle and driver.")
    dep=datetime.fromisoformat(data['departure_utc'].replace('Z','+00:00'))
    end=(dep+timedelta(minutes=rt['duration_min'])).strftime('%Y-%m-%dT%H:%M:%SZ')
    collision=row("SELECT id FROM trips WHERE id<>? AND status<>'Cancelled' AND (vehicle_id=? OR driver_id=?) AND departure_utc<? AND expected_arrival_utc>? LIMIT 1",(existing['id'] if existing else -1,v['id'],driver['id'],end,data['departure_utc']),con)
    if collision: raise HTTPException(409,f"Vehicle or driver overlaps trip {collision['id']}.")
    if existing and existing['passenger_count']>v['capacity']: raise HTTPException(409,"Assigned vehicle is too small for existing reservations.")
    return data | {"expected_arrival_utc":end,"capacity":v['capacity']} | ({} if existing else {"code":"SM-"+secrets.token_hex(4).upper(),"passenger_count":0,"delay_min":0,"revenue_cents":0,"operating_cost_cents":int(rt['distance_km']*110),"fuel_liters":None,"weather_index":.3,"congestion_index":.5,"peak_hour":int(dep.hour in [7,8,17,18])})


def book(con,data,user):
    if user['role']=='Customer': data['customer_id']=user['customer_id']
    tr=row("SELECT t.*,r.fare_cents FROM trips t JOIN routes r ON t.route_id=r.id WHERE t.id=?",(data['trip_id'],),con)
    if not tr or tr['status']!='Scheduled': raise HTTPException(409,"Only scheduled trips can be booked in this synthetic calendar.")
    seats=int(data['seats'])
    actual=scalar("SELECT COALESCE(SUM(seats),0) FROM reservations WHERE trip_id=? AND status<>'Cancelled'",(tr['id'],),con)
    if actual+seats>tr['capacity']: raise HTTPException(409,"Not enough seats remain.")
    if not row('SELECT id FROM customers WHERE id=?',(data['customer_id'],),con): raise HTTPException(422,"Customer not found.")
    data |= {'price_cents':seats*tr['fare_cents'],'status':'Booked','created_at':utcnow()}
    cur=con.execute("INSERT INTO reservations(customer_id,trip_id,seats,price_cents,status,created_at) VALUES(?,?,?,?,?,?)",tuple(data[k] for k in ['customer_id','trip_id','seats','price_cents','status','created_at']))
    rid=cur.lastrowid
    con.execute('INSERT INTO tickets(reservation_id,reference,status) VALUES(?,?,?)',(rid,'SMT-'+secrets.token_hex(5).upper(),'Issued'))
    con.execute('INSERT INTO payments(reservation_id,amount_cents,status,created_at) VALUES(?,?,?,?)',(rid,data['price_cents'],'Simulated paid',utcnow()))
    con.execute('UPDATE trips SET passenger_count=passenger_count+?,revenue_cents=revenue_cents+? WHERE id=?',(seats,data['price_cents'],tr['id']))
    return rid


@router.post('/resources/{resource}')
async def create_resource(resource:str,request:Request):
    if resource not in DEFS or resource=='payments': raise HTTPException(404)
    user=require(request,resource,'create')
    payload=await request.json()
    if not isinstance(payload,dict): raise HTTPException(422)
    if resource in ['reservations','complaints'] and user['role']=='Customer': payload['customer_id']=user['customer_id']
    data=validate(DEFS[resource],payload)
    with transaction() as con:
        cross_validate(con,resource,data,user)
        if resource=='reservations': identifier=book(con,data,user)
        else:
            if resource=='trips': data=make_trip(con,data)
            if resource=='incidents': data['reported_by']=user['id']
            if resource=='complaints': data['created_at']=utcnow()
            if resource=='documents': data['updated_at']=utcnow()
            columns=','.join(data)
            cur=con.execute(f"INSERT INTO {DEFS[resource]['table']} ({columns}) VALUES ({','.join('?' for _ in data)})",list(data.values()))
            identifier=cur.lastrowid
            if resource=='routes':
                con.executemany('INSERT INTO route_stops VALUES(?,?,?)',[(identifier,data['origin_id'],0),(identifier,data['destination_id'],1)])
        audit(con,user,'create',resource,identifier,after=data,request=request)
    return {'id':identifier,'message':'Saved. Analytical exports refresh on the next ETL run.'}


@router.patch('/resources/{resource}/{identifier}')
async def update_resource(resource:str,identifier:int,request:Request):
    if resource not in DEFS or resource in ['payments','reservations']: raise HTTPException(404)
    user=require(request,resource,'modify'); payload=await request.json()
    if not isinstance(payload,dict) or not payload: raise HTTPException(422)
    if user['role']=='Driver' and (resource!='trips' or set(payload)-{'status'}): raise HTTPException(403,"Drivers may update assigned trip status only.")
    patch=validate(DEFS[resource],payload,partial=True)
    with transaction() as con:
        before=assert_owned(con,user,resource,identifier)
        data=before|patch
        cross_validate(con,resource,data,user)
        if resource=='trips':
            old=before['status'];new=data['status']
            if user['role']=='Driver' and (old,new) not in [('Scheduled','In progress'),('In progress','Completed')]: raise HTTPException(409,"Allowed transitions: Scheduled → In progress → Completed.")
            if any(k in patch for k in ['vehicle_id','driver_id','route_id','departure_utc']):
                if old!='Scheduled': raise HTTPException(409,"Only scheduled trips can be reassigned.")
                patch=make_trip(con,{k:data[k] for k in DEFS['trips']['fields']},before)
            if new=='Cancelled' and old!='Cancelled':
                if old!='Scheduled': raise HTTPException(409,"Only scheduled trips can be cancelled.")
                con.execute("UPDATE payments SET status='Simulated refund' WHERE reservation_id IN (SELECT id FROM reservations WHERE trip_id=?)",(identifier,))
                con.execute("UPDATE tickets SET status='Voided' WHERE reservation_id IN (SELECT id FROM reservations WHERE trip_id=?)",(identifier,))
                con.execute("UPDATE reservations SET status='Cancelled' WHERE trip_id=?",(identifier,))
                patch |= {'passenger_count':0,'revenue_cents':0,'delay_min':0}
            if new=='Completed' and old!='Completed':
                completed=utcnow();expected=datetime.fromisoformat(data['expected_arrival_utc'].replace('Z','+00:00'))
                patch |= {'actual_arrival_utc':completed,'delay_min':max(0,(datetime.now(timezone.utc)-expected).total_seconds()/60)}
                con.execute("UPDATE reservations SET status='Completed' WHERE trip_id=? AND status='Booked'",(identifier,))
            if old in ['Completed','Cancelled'] and new!=old: raise HTTPException(409,"Closed trips cannot be reopened.")
        if resource=='routes' and any(k in patch for k in ['origin_id','destination_id']):
            con.execute('DELETE FROM route_stops WHERE route_id=?',(identifier,))
            con.executemany('INSERT INTO route_stops VALUES(?,?,?)',[(identifier,data['origin_id'],0),(identifier,data['destination_id'],1)])
        if resource=='documents':patch['updated_at']=utcnow()
        con.execute(f"UPDATE {DEFS[resource]['table']} SET "+','.join(k+'=?' for k in patch)+' WHERE id=?',list(patch.values())+[identifier])
        audit(con,user,'modify',resource,identifier,before=before,after=patch,request=request)
    return {'message':'Changes saved.'}


@router.post('/reservations/{identifier}/cancel')
def cancel_reservation(identifier:int,request:Request):
    user=require(request,'reservations','modify')
    with transaction() as con:
        before=assert_owned(con,user,'reservations',identifier)
        if before['status']!='Booked': raise HTTPException(409,'Only a booked reservation can be cancelled.')
        trip=row('SELECT status FROM trips WHERE id=?',(before['trip_id'],),con)
        if trip['status']!='Scheduled': raise HTTPException(409,'This trip has already started or closed.')
        con.execute("UPDATE reservations SET status='Cancelled' WHERE id=?",(identifier,))
        con.execute("UPDATE payments SET status='Simulated refund' WHERE reservation_id=?",(identifier,))
        con.execute("UPDATE tickets SET status='Voided' WHERE reservation_id=?",(identifier,))
        con.execute('UPDATE trips SET passenger_count=passenger_count-?,revenue_cents=revenue_cents-? WHERE id=?',(before['seats'],before['price_cents'],before['trip_id']))
        audit(con,user,'cancel','reservations',identifier,before,{'status':'Cancelled'},request)
    return {'message':'Reservation cancelled; sandbox payment refunded. No real money moved.'}


@router.get('/reservations/{identifier}/ticket')
def ticket(identifier:int,request:Request):
    user=require(request,'reservations')
    with transaction() as con:
        res=assert_owned(con,user,'reservations',identifier)
        details=row('SELECT r.name,t.departure_utc,k.reference,k.status FROM trips t JOIN routes r ON r.id=t.route_id JOIN tickets k ON k.reservation_id=? WHERE t.id=?',(identifier,res['trip_id']),con)
    return res|details|{'notice':'SYNTHETIC DEMO TICKET — not valid for travel. No real payment.'}


@router.delete('/resources/{resource}/{identifier}')
def delete_resource(resource:str,identifier:int,request:Request,confirm:bool=False):
    if resource not in DEFS:raise HTTPException(404)
    user=require(request,resource,'delete')
    if not confirm:raise HTTPException(422,'Explicit confirmation is required.')
    if resource in ['trips','reservations','payments','incidents','maintenance','complaints']:
        raise HTTPException(409,'Operational records are retained for audit. Close or cancel the record instead.')
    with transaction() as con:
        before=assert_owned(con,user,resource,identifier)
        con.execute(f"DELETE FROM {DEFS[resource]['table']} WHERE id=?",(identifier,))
        audit(con,user,'delete',resource,identifier,before=before,request=request)
    return {'message':'Record deleted.'}


@router.post('/maintenance/{identifier}/parts')
async def consume_part(identifier:int,request:Request):
    user=require(request,'maintenance','modify');payload=await request.json()
    try:part_id=int(payload['part_id']);qty=int(payload['quantity'])
    except (KeyError,ValueError,TypeError):raise HTTPException(422,'Provide part_id and quantity.')
    if qty<=0 or qty>1000:raise HTTPException(422,'Quantity must be 1–1000.')
    with transaction() as con:
        work=row('SELECT * FROM maintenance WHERE id=?',(identifier,),con)
        part=row('SELECT * FROM parts WHERE id=?',(part_id,),con)
        if not work or not part:raise HTTPException(404)
        if work['status']=='Completed' or part['quantity']<qty:raise HTTPException(409,'Closed work order or insufficient stock.')
        con.execute('UPDATE parts SET quantity=quantity-? WHERE id=?',(qty,part_id))
        existing=row('SELECT quantity FROM work_order_parts WHERE maintenance_id=? AND part_id=?',(identifier,part_id),con)
        if existing:con.execute('UPDATE work_order_parts SET quantity=quantity+? WHERE maintenance_id=? AND part_id=?',(qty,identifier,part_id))
        else:con.execute('INSERT INTO work_order_parts VALUES(?,?,?)',(identifier,part_id,qty))
        con.execute('UPDATE maintenance SET cost_cents=cost_cents+? WHERE id=?',(qty*part['unit_cost_cents'],identifier))
        audit(con,user,'consume_part','maintenance',identifier,after={'part_id':part_id,'quantity':qty},request=request)
    return {'message':'Parts consumed and work-order cost updated.'}
