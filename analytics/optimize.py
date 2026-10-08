import math


def allocate(routes,vehicles,drivers_available,use_milp=True):
    if not routes or not vehicles:return {'allocations':[],'unserved':sum(r['demand'] for r in routes),'method':'No available resources'}
    v=vehicles[:40];r=routes[:22]
    if use_milp:
        import numpy as np
        from scipy.optimize import milp,Bounds,LinearConstraint
        n=len(v)*len(r);total=n+len(r)
        c=np.zeros(total)
        for i,vehicle in enumerate(v):
            for j,route in enumerate(r):c[i*len(r)+j]=route['distance_km']*.55+50
        c[n:]=1000
        upper=np.ones(total);upper[n:]=np.inf
        for i,vehicle in enumerate(v):
            for j,route in enumerate(r):
                if route['duration_min']>480:upper[i*len(r)+j]=0
        A=[];lo=[];hi=[]
        for i in range(len(v)):
            a=np.zeros(total);a[i*len(r):(i+1)*len(r)]=1;A.append(a);lo.append(-np.inf);hi.append(1)
        a=np.zeros(total);a[:n]=1;A.append(a);lo.append(-np.inf);hi.append(drivers_available)
        for j,route in enumerate(r):
            a=np.zeros(total)
            for i,vehicle in enumerate(v):a[i*len(r)+j]=vehicle['capacity']
            a[n+j]=1;A.append(a);lo.append(route['demand']);hi.append(np.inf)
        result=milp(c,integrality=np.r_[np.ones(n),np.zeros(len(r))],bounds=Bounds(np.zeros(total),upper),constraints=LinearConstraint(np.array(A),lo,hi),options={'time_limit':5})
        if result.x is not None:
            allocations=[{'vehicle':v[i]['code'],'route':r[j]['name'],'route_id':r[j]['id'],'seats':v[i]['capacity']} for i in range(len(v)) for j in range(len(r)) if result.x[i*len(r)+j]>.5]
            return {'allocations':allocations,'unserved':round(float(sum(result.x[n:])),1),'method':'Mixed-integer linear optimization (HiGHS)','optimal':bool(result.success),'objective':float(result.fun),'solver_message':str(result.message),'constraints':['At most one assignment per vehicle in the planning window','Assignments cannot exceed available drivers','Single-trip duration ≤ 480 minutes (illustrative constraint, not a legal-hours rule)','Demand coverage includes explicit unserved-passenger slack'],'limitation':'Planning scenario only. Does not model full driver rosters, geography/deadheading, qualifications or regulatory rest rules. Dispatch must review. No assignments are applied automatically.'}
    remaining={x['id']:x['demand'] for x in r};alloc=[]
    for vehicle in sorted(v,key=lambda x:-x['capacity'])[:drivers_available]:
        candidates=[x for x in r if remaining[x['id']]>0 and x['duration_min']<=480]
        if not candidates:break
        route=max(candidates,key=lambda x:remaining[x['id']])
        alloc.append({'vehicle':vehicle['code'],'route':route['name'],'route_id':route['id'],'seats':vehicle['capacity']})
        remaining[route['id']]=max(0,remaining[route['id']]-vehicle['capacity'])
    return {'allocations':alloc,'unserved':sum(remaining.values()),'method':'Greedy feasible baseline','optimal':False,'limitation':'Install analytics dependencies for MILP. This baseline ignores roster and deadheading constraints; no automatic dispatch.'}
