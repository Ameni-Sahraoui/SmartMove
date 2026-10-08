import argparse
import csv
import math
import random
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from .config import AS_OF, DATA, DATASET_VERSION, DB
from .database import schema

STATIONS = [
    (1, "Pacific Central", "Vancouver", "British Columbia", 49.28, -123.12, "Hub", 1),
    (2, "Thompson Terminal", "Kamloops", "British Columbia", 50.67, -120.33, "Terminal", 1),
    (3, "Foothills Exchange", "Calgary", "Alberta", 51.05, -114.07, "Hub", 1),
    (4, "Northern Gateway", "Edmonton", "Alberta", 53.55, -113.49, "Hub", 1),
    (5, "Prairie Centre", "Regina", "Saskatchewan", 50.45, -104.62, "Terminal", 1),
    (6, "River Landing", "Saskatoon", "Saskatchewan", 52.13, -106.67, "Terminal", 1),
    (7, "Union Exchange", "Winnipeg", "Manitoba", 49.90, -97.14, "Hub", 1),
    (8, "Wheat City Terminal", "Brandon", "Manitoba", 49.85, -99.95, "Terminal", 1),
    (9, "Lakeshore Hub", "Toronto", "Ontario", 43.65, -79.38, "Hub", 1),
    (10, "Capital Exchange", "Ottawa", "Ontario", 45.42, -75.70, "Terminal", 1),
    (11, "Métropole Hub", "Montréal", "Quebec", 45.50, -73.57, "Hub", 1),
    (12, "Capitale Terminal", "Québec", "Quebec", 46.81, -71.21, "Hub", 1),
]
ROUTE_PAIRS = [(1,2,354,280,5600),(2,3,620,470,8500),(3,4,299,200,4200),(4,6,523,395,7200),
               (6,5,258,185,3900),(5,8,360,270,5100),(8,7,197,155,3300),
               (9,10,450,290,6200),(10,11,199,145,3400),(11,12,255,190,4500),(9,11,540,355,7800)]


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate(path=DB, seed=42, history_days=548):
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        with sqlite3.connect(path) as existing:
            try:
                if existing.execute("SELECT value FROM meta WHERE key='seed_complete'").fetchone():
                    return
            except sqlite3.OperationalError:
                pass
    path.parent.mkdir(parents=True, exist_ok=True)
    schema(path)
    rng = random.Random(seed)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    end = date.fromisoformat(AS_OF)
    start = end - timedelta(days=history_days - 1)
    con.executemany("INSERT INTO meta VALUES(?,?)", [("as_of", AS_OF), ("dataset_version", DATASET_VERSION), ("seed", str(seed)), ("schema_version","1"), ("synthetic","true")])
    con.executemany("INSERT INTO facilities VALUES(?,?,?,?,?,?,?,?)", STATIONS)
    customers = [(i, f"Passenger {i:05d}", f"passenger{i:05d}@smartmove.example", rng.choice(STATIONS)[3], rng.choices(["Standard","Silver","Gold"],[.64,.25,.11])[0], stamp(datetime.combine(start-timedelta(days=rng.randint(2,700)),datetime.min.time()))) for i in range(1,12001)]
    con.executemany("INSERT INTO customers VALUES(?,?,?,?,?,?)", customers)
    employees = [(i, f"EMP-{i:04d}", f"Driver {i:03d}" if i<=160 else f"Engineer {i-160:02d}", "Driver" if i<=160 else "Engineer", (i-1)%12+1,1) for i in range(1,181)]
    con.executemany("INSERT INTO employees VALUES(?,?,?,?,?,?)", employees)
    route_data = []
    for pair in ROUTE_PAIRS:
        for a,b in [(pair[0],pair[1]),(pair[1],pair[0])]:
            i=len(route_data)+1
            route_data.append((i,f"{STATIONS[a-1][2]} → {STATIONS[b-1][2]}",a,b,pair[2],pair[3],pair[4],"Active"))
    con.executemany("INSERT INTO routes VALUES(?,?,?,?,?,?,?,?)",route_data)
    con.executemany("INSERT INTO route_stops VALUES(?,?,?)", [(r[0],s,o) for r in route_data for o,s in enumerate([r[2],r[3]])])
    con.executemany("INSERT INTO schedules VALUES(?,?,?,?)", [(i*3+j+1,r[0],h,"Mon–Sun") for i,r in enumerate(route_data) for j,h in enumerate([7,12,18])])
    vehicle_data=[]
    for i in range(1,97):
        typ,cap=("Coach",56) if i<=40 else ("Transit Bus",46) if i<=72 else ("Minibus",22) if i<=88 else ("Paratransit",12)
        vehicle_data.append((i,f"{'MV' if typ=='Coach' else 'TR' if typ=='Transit Bus' else 'PB'}-{7800+i}",typ,cap,(i-1)%12+1,rng.choices(["Active","Standby","Maintenance"],[.83,.09,.08])[0],rng.randint(14000,260000),rng.choices(["Diesel","Electric","Hybrid"],[.50,.22,.28])[0],(end-timedelta(days=rng.randint(8,95))).isoformat()))
    con.executemany("INSERT INTO vehicles VALUES(?,?,?,?,?,?,?,?,?)",vehicle_data)
    trows=[]; rrows=[]; prows=[]; tkrows=[]; surveys=[]; complaints=[]; incidents=[]
    vfree={v[0]:datetime.min for v in vehicle_data}; dfree={e[0]:datetime.min for e in employees if e[3]=="Driver"}
    reservation_id=0
    for day_n in range(history_days+8):
        d=start+timedelta(days=day_n)
        future=d>end
        season=1+.12*math.sin(2*math.pi*(d.timetuple().tm_yday-130)/365.25)+.00027*day_n
        for hr in [7,12,18]:
            for rt in route_data:
                if hr==12 and rt[0]%3==0:
                    continue
                dep=datetime.combine(d,datetime.min.time())+timedelta(hours=hr,minutes=(rt[0]%4)*10)
                possible=[v for v in vehicle_data if vfree[v[0]]<=dep and (not future or v[5]=="Active")]
                v=rng.choice(possible or vehicle_data)
                drs=[dr for dr in dfree if dfree[dr]<=dep]
                driver=rng.choice(drs)
                arrival=dep+timedelta(minutes=rt[5])
                vfree[v[0]]=arrival+timedelta(minutes=45)
                dfree[driver]=arrival+timedelta(minutes=90)
                traffic=min(1,max(0,rng.gauss(.42+(.16 if hr in (7,18) else 0),.18)))
                weather=min(1,max(0,rng.betavariate(2,6)+(.16 if d.month in [1,2,12] else 0)))
                delay=max(0, rng.gauss(2+traffic*10+weather*12+(5 if rt[5]>350 else 0),6))
                if rng.random()<.035:
                    delay+=rng.uniform(20,70)
                status="Scheduled" if future else "Cancelled" if rng.random()<.027 else "Completed"
                if d==end and hr==18:
                    status="In progress" if rt[0]%3 else "Completed"
                occ=min(.99,max(.14,rng.gauss(.65*season*(1.10 if d.weekday() in [4,6] else 1),.13)))
                count=round(v[3]*occ*(.70 if future else 1)) if status!="Cancelled" else 0
                if status=="Cancelled": delay=0
                tid=len(trows)+1
                revenue=count*rt[6]
                cost=int(rt[4]*rng.uniform(85,140)+(rng.uniform(100,250)*rt[5]/60)) if status!="Cancelled" else 2000
                fuel=round(rt[4]*rng.uniform(.16,.27),2) if v[7]!="Electric" else 0
                if rng.random()<.012: fuel=None
                trows.append((tid,f"SM-{tid:06d}",rt[0],v[0],driver,stamp(dep),stamp(arrival),stamp(arrival+timedelta(minutes=delay)) if status=="Completed" else None,status,count,v[3],round(delay,2) if status in ["Completed","In progress"] else 0,revenue,cost,fuel,round(weather,3),round(traffic,3),int(hr in [7,18])))
                remaining=count
                if status=="Cancelled": remaining=rng.randint(3,max(4,v[3]//2))
                while remaining>0:
                    seats=min(remaining,rng.choices([1,2,3,4,5,6],[.12,.26,.21,.20,.12,.09])[0])
                    remaining-=seats; reservation_id+=1
                    customer=rng.randrange(1,len(customers)+1)
                    booked=stamp(dep-timedelta(days=rng.randint(1,30),hours=rng.randint(1,9)))
                    state="Cancelled" if status=="Cancelled" else "Completed" if status=="Completed" else "Booked"
                    rrows.append((reservation_id,customer,tid,seats,seats*rt[6],state,booked))
                    prows.append((reservation_id,reservation_id,seats*rt[6],"Simulated refund" if state=="Cancelled" else "Simulated paid",booked))
                    tkrows.append((reservation_id,reservation_id,f"SMT-{reservation_id:07d}","Voided" if state=="Cancelled" else "Issued"))
                    if status=="Completed" and rng.random()<.06:
                        score=max(1,min(5,round(rng.gauss(4.7-delay*.033,.65))))
                        surveys.append((len(surveys)+1,customer,tid,score,stamp(arrival+timedelta(hours=4))))
                    if status in ["Completed","Cancelled"] and rng.random()<.008:
                        cat=rng.choice(["Delay","Accessibility","Communication","Cleanliness","Ticketing"])
                        complaints.append((len(complaints)+1,customer,tid,cat,f"Synthetic feedback about {cat.lower()} on trip {tid}.",rng.choice(["Resolved","Resolved","Open","Investigating"]),stamp(arrival+timedelta(hours=3))))
                if not future and status!="Cancelled" and rng.random()<.012:
                    itype=rng.choice(["Road construction","Heavy congestion","Vehicle breakdown","Severe weather","Service disruption"])
                    incidents.append((len(incidents)+1,tid,v[0],None,stamp(dep+timedelta(minutes=30)),STATIONS[rt[2]-1][2],itype,"High" if itype=="Vehicle breakdown" else "Medium", "Active" if day_n>=history_days-2 and rng.random()<.6 else "Resolved",f"Fictional {itype.lower()} report; supervisor review recorded."))
    con.executemany("INSERT INTO trips VALUES("+','.join('?'*18)+")",trows)
    con.executemany("INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",rrows)
    con.executemany("INSERT INTO payments VALUES(?,?,?,?,?)",prows)
    con.executemany("INSERT INTO tickets VALUES(?,?,?,?)",tkrows)
    con.executemany("INSERT INTO satisfaction VALUES(?,?,?,?,?)",surveys)
    con.executemany("INSERT INTO complaints VALUES(?,?,?,?,?,?,?)",complaints)
    con.executemany("INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?,?,?)",incidents)
    mrows=[]; telem=[]
    issues=[("Preventive","Scheduled preventive service"),("Brakes","Brake assembly inspection"),("Battery","Battery voltage check"),("Engine","Engine temperature inspection"),("Tires","Tire condition review")]
    for v in vehicle_data:
        for j in range(6):
            md=end-timedelta(days=20+j*70+rng.randint(0,35))
            cat,summary=rng.choice(issues)
            mrows.append((len(mrows)+1,v[0],rng.randint(161,180),md.isoformat(),(md+timedelta(days=rng.randint(1,3))).isoformat(),cat,"Completed",rng.randint(15000,225000),summary+" — synthetic record"))
        if v[5]=="Maintenance":
            cat,summary=rng.choice(issues)
            mrows.append((len(mrows)+1,v[0],rng.randint(161,180),end.isoformat(),None,cat,"Open",0,summary+" — requires engineer review"))
        for dd in range(0,history_days,7):
            snapshot=start+timedelta(days=dd)
            wear=max(0,min(100,rng.gauss(39+(dd%63)*.38,16)))
            temp=rng.gauss(87+(5 if v[2]=="Coach" else 0),8)
            volt=rng.gauss(12.55,.57)
            kms=rng.uniform(500,16000)
            vib=abs(rng.gauss(2,.8))
            z=-4.5+.075*(temp-80)+.033*wear+1.3*max(0,12.1-volt)+.00007*kms+.31*vib
            prob=1/(1+math.exp(-z))
            label=int(rng.random()<prob) if snapshot+timedelta(days=7)<=end else None
            telem.append((len(telem)+1,v[0],snapshot.isoformat(),round(temp,2),round(wear,2),round(volt,2),round(kms,1),round(vib,3),label))
    con.executemany("INSERT INTO maintenance VALUES(?,?,?,?,?,?,?,?,?)",mrows)
    con.executemany("INSERT INTO telemetry VALUES(?,?,?,?,?,?,?,?,?)",telem)
    con.executemany("INSERT INTO parts VALUES(?,?,?,?)",[(1,"Brake pad kit",42,12500),(2,"Air filter",76,3200),(3,"Battery module",15,84500),(4,"Tire assembly",32,36500)])
    con.executemany("INSERT INTO documents VALUES(?,?,?,?,?)",[(1,"Operating prototype boundaries","Governance","Use only synthetic data. Vehicle assignments are operational estimates and require dispatch review. No real payments or GPS feed are connected.",AS_OF),(2,"Incident reporting workflow","Operations","Drivers report assigned-trip incidents. Supervisors review severity. Engineers manage technical work orders. Do not use this prototype to coordinate emergencies.",AS_OF),(3,"BI data dictionary","Analytics","See docs/DATA_DICTIONARY.md and powerbi/README.md in the project package.",AS_OF)])
    con.executemany("INSERT INTO notifications VALUES(?,?,?,?,?,?)",[(1,None,"Manager","Review today's service board","Open incidents and scheduled trips are ready for supervisor review.",AS_OF),(2,None,"Engineer","Maintenance review queue","Review model risk together with telemetry and maintenance records.",AS_OF),(3,None,"Analyst","Synthetic dataset loaded",f"Dataset {DATASET_VERSION}; rebuild ETL after changing records.",AS_OF)])
    con.execute("INSERT OR REPLACE INTO meta VALUES('seed_complete','true')")
    con.commit()
    if con.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Synthetic data failed foreign key validation")
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    with (path.parent/"staging_fuel.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f); writer.writerow(["trip_id","fuel_liters"])
        for i,tr in enumerate(trows[:600]):
            writer.writerow([tr[0], -10 if i==8 else "" if i%53==0 else tr[14] or 0])
        writer.writerow([1,30]); writer.writerow([999999,12]); writer.writerow([2,"not-a-number"])
    print(f"Created synthetic dataset: {len(trows):,} trips, {len(rrows):,} reservations, {len(vehicle_data)} vehicles, {len(telem):,} telemetry snapshots.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,default=DB)
    parser.add_argument("--days",type=int,default=548)
    args=parser.parse_args()
    generate(args.db,history_days=args.days)
