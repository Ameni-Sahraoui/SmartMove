import csv
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from smartmove.config import DATA, DB, EXPORTS, ARTIFACTS, DATASET_VERSION


def write_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,indent=2,default=str),encoding='utf-8')
    os.replace(temporary,path)


def quality(db=DB):
    con=sqlite3.connect(db);con.row_factory=sqlite3.Row
    tests=[]
    checks=[
      ('Referential integrity','PRAGMA foreign_key_check','critical'),
      ('Seat capacity','SELECT id FROM trips WHERE passenger_count>capacity OR passenger_count<0','critical'),
      ('Reservation reconciliation',"SELECT t.id FROM trips t WHERE t.passenger_count<>(SELECT COALESCE(SUM(r.seats),0) FROM reservations r WHERE r.trip_id=t.id AND r.status<>'Cancelled')",'critical'),
      ('Revenue reconciliation',"SELECT t.id FROM trips t WHERE t.revenue_cents<>(SELECT COALESCE(SUM(r.price_cents),0) FROM reservations r WHERE r.trip_id=t.id AND r.status<>'Cancelled')",'critical'),
      ('Arrival sequence','SELECT id FROM trips WHERE expected_arrival_utc<=departure_utc OR (actual_arrival_utc IS NOT NULL AND actual_arrival_utc<departure_utc)','critical'),
      ('Vehicle schedule overlap',"SELECT t.id FROM trips t JOIN trips u ON t.vehicle_id=u.vehicle_id AND t.id<u.id AND t.status<>'Cancelled' AND u.status<>'Cancelled' AND t.departure_utc<u.expected_arrival_utc AND u.departure_utc<t.expected_arrival_utc",'critical'),
      ('Driver schedule overlap',"SELECT t.id FROM trips t JOIN trips u ON t.driver_id=u.driver_id AND t.id<u.id AND t.status<>'Cancelled' AND u.status<>'Cancelled' AND t.departure_utc<u.expected_arrival_utc AND u.departure_utc<t.expected_arrival_utc",'critical'),
      ('Missing fuel readings','SELECT id FROM trips WHERE fuel_liters IS NULL','warning'),
      ('Maintenance date order','SELECT id FROM maintenance WHERE completed_at<opened_at','critical'),
      ('Survey range','SELECT id FROM satisfaction WHERE score<1 OR score>5','critical')]
    for name,sql,severity in checks:
        found=con.execute(sql).fetchall()
        tests.append({'check':name,'issues':len(found),'severity':severity,'status':'Pass' if not found else 'Review' if severity=='warning' else 'Fail','sample_ids':[x[0] for x in found[:8]]})
    totals={t:con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['customers','facilities','vehicles','trips','reservations','payments','telemetry','maintenance','incidents','satisfaction']}
    staged=[];source=Path(db).parent/'staging_fuel.csv';seen=set()
    valid_trip_ids={x[0] for x in con.execute('SELECT id FROM trips')}
    if source.exists():
        with source.open(encoding='utf-8-sig',newline='') as f:
            for n,r in enumerate(csv.DictReader(f),2):
                reason=[]
                try:
                    tid=int(r['trip_id'])
                    if tid not in valid_trip_ids:reason.append('Unknown trip key')
                    if tid in seen:reason.append('Duplicate trip key')
                    seen.add(tid)
                except (ValueError,KeyError,TypeError):reason.append('Invalid trip key')
                try:
                    x=float(r['fuel_liters'])
                    if not __import__('math').isfinite(x) or x<0:reason.append('Impossible fuel quantity')
                except (ValueError,KeyError,TypeError):reason.append('Missing or nonnumeric fuel')
                if reason:staged.append({'line':n,'trip_id':r.get('trip_id'),'reason':'; '.join(reason)})
    con.close()
    return {'dataset_version':DATASET_VERSION,'checked_at':datetime.now(timezone.utc).isoformat(),'checks':tests,'counts':totals,'quarantine':staged,'critical_pass':all(x['issues']==0 for x in tests if x['severity']=='critical'),'notice':'Staging data is isolated; invalid imported rows never overwrite operational records. Missing fuel remains NULL; it is not silently converted to zero.'}


def run_etl(db=DB,exports=EXPORTS,artifacts=ARTIFACTS):
    exports=Path(exports);exports.mkdir(parents=True,exist_ok=True)
    report=quality(db)
    write_json(Path(artifacts)/'quality.json',report)
    with (exports/'quarantine.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['line','trip_id','reason']);w.writeheader();w.writerows(report['quarantine'])
    if not report['critical_pass']:raise ValueError('Critical data checks failed. Warehouse not refreshed.')
    final=Path(db).parent/'warehouse.db';temp=final.with_suffix('.building.db')
    if temp.exists():temp.unlink()
    con=sqlite3.connect(temp)
    con.execute('ATTACH DATABASE ? AS src',(str(Path(db).resolve()),))
    con.executescript('''
CREATE TABLE dim_date AS SELECT DISTINCT CAST(replace(substr(departure_utc,1,10),'-','') AS INTEGER) date_key,substr(departure_utc,1,10) date,CAST(substr(departure_utc,1,4) AS INTEGER) year,CAST(substr(departure_utc,6,2) AS INTEGER) month,CAST(strftime('%w',departure_utc) AS INTEGER) weekday FROM src.trips;
CREATE UNIQUE INDEX pk_dim_date ON dim_date(date_key);
CREATE TABLE dim_time AS SELECT DISTINCT CAST(substr(departure_utc,12,2) AS INTEGER)*60+CAST(substr(departure_utc,15,2) AS INTEGER) time_key,substr(departure_utc,12,5) time FROM src.trips;
CREATE TABLE dim_vehicle AS SELECT * FROM src.vehicles;
CREATE TABLE dim_driver AS SELECT id,code,name,facility_id FROM src.employees WHERE job='Driver';
CREATE TABLE dim_station AS SELECT * FROM src.facilities;
CREATE TABLE dim_location AS SELECT DISTINCT province,city,latitude,longitude FROM src.facilities;
CREATE TABLE dim_customer AS SELECT id,province,loyalty_tier FROM src.customers;
CREATE TABLE dim_route AS SELECT r.*,a.city origin_city,a.province,b.city destination_city FROM src.routes r JOIN src.facilities a ON a.id=r.origin_id JOIN src.facilities b ON b.id=r.destination_id;
CREATE TABLE fact_trip AS SELECT t.*,CAST(replace(substr(departure_utc,1,10),'-','') AS INTEGER) date_key,CAST(substr(departure_utc,12,2) AS INTEGER)*60+CAST(substr(departure_utc,15,2) AS INTEGER) time_key,CASE WHEN status='Completed' AND delay_min<=15 THEN 1 ELSE 0 END on_time,CASE WHEN status='Completed' THEN 1 ELSE 0 END completed,CAST(revenue_cents-operating_cost_cents AS REAL)/100 profit_cad FROM src.trips t;
CREATE UNIQUE INDEX pk_fact_trip ON fact_trip(id);
CREATE TABLE fact_reservation AS SELECT * FROM src.reservations;
CREATE TABLE fact_payment AS SELECT * FROM src.payments;
CREATE TABLE fact_maintenance AS SELECT * FROM src.maintenance;
CREATE TABLE fact_incident AS SELECT id,trip_id,vehicle_id,incident_time,location,type,severity,status FROM src.incidents;
CREATE TABLE fact_satisfaction AS SELECT * FROM src.satisfaction;
CREATE TABLE fact_route_daily AS SELECT date_key,route_id,COUNT(*) trips,SUM(passenger_count) passengers,SUM(capacity) seat_capacity,SUM(revenue_cents)/100.0 revenue_cad,SUM(operating_cost_cents)/100.0 cost_cad,AVG(delay_min) avg_delay_min,SUM(on_time) on_time_trips,SUM(completed) completed_trips FROM fact_trip GROUP BY date_key,route_id;
''')
    tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    manifest=[]
    for table in tables:
        cur=con.execute(f'SELECT * FROM {table}')
        filepath=exports/f'{table}.csv'
        with filepath.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow([c[0] for c in cur.description]);writer.writerows(cur)
        n=con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        manifest.append({'table':table,'rows':n,'file':filepath.name})
    con.commit();con.close();os.replace(temp,final)
    write_json(Path(artifacts)/'etl.json',{'run_at':datetime.now(timezone.utc).isoformat(),'dataset_version':DATASET_VERSION,'tables':manifest,'quality':report['critical_pass'],'mode':'Full snapshot; operational database unchanged; customer names and emails excluded from warehouse dimensions.'})
    return manifest


if __name__=='__main__':
    print(json.dumps(run_etl(),indent=2))
