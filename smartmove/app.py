import asyncio
import csv
import io
import json
import logging
import os
import secrets
import sqlite3
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from fastapi import FastAPI,HTTPException,Request,BackgroundTasks
from fastapi.responses import JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,ConfigDict
from . import config
from .database import connect,row,rows,scalar,transaction,audit,utcnow
from .security import bootstrap,current_user,public_user,require,allowed,csrf_check,rate_limit,token_hash,password_ok,HASHER,issue_account_token,ROLES,MODULES,ACTIONS,VerificationError,InvalidHashError
from .resources import router as resource_router
from .insights import router as insight_router


@asynccontextmanager
async def lifespan(app):
    from .seed import generate
    generate()
    bootstrap()
    with transaction() as con:
        con.execute("DELETE FROM sessions WHERE expires_at<?",(utcnow(),))
        con.execute("UPDATE jobs SET status='Interrupted',finished_at=? WHERE status='Running'",(utcnow(),))
    yield


app=FastAPI(title='SmartMove Operational API',version='1.0.0',description='Synthetic transportation operations prototype. Cookie authentication + backend RBAC. Not a live transport or payment service.',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(resource_router);app.include_router(insight_router)
logger=logging.getLogger('smartmove')


@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(request,exc):
    return JSONResponse({'detail':'This change violates a data relationship or uniqueness rule. Check references; existing operational history cannot be deleted.'},status_code=409)


@app.exception_handler(Exception)
async def internal_error(request,exc):
    logger.exception('Request failed')
    return JSONResponse({'detail':'The operation could not be completed. Check the server log; no sensitive error details are returned.'},status_code=500)


@app.middleware('http')
async def security_headers(request,call_next):
    try:
        body_length=int(request.headers.get('content-length','0') or 0)
    except ValueError:
        return JSONResponse({'detail':'Invalid Content-Length.'},status_code=400)
    if body_length<0:
        return JSONResponse({'detail':'Invalid Content-Length.'},status_code=400)
    if body_length>1048576:
        return JSONResponse({'detail':'Request too large; maximum 1 MiB.'},status_code=413)
    if request.url.path.startswith('/api/') and request.method in ['POST','PUT','PATCH','DELETE']:
        try:csrf_check(request)
        except HTTPException as e:return JSONResponse({'detail':e.detail},status_code=e.status_code)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Permissions-Policy']='geolocation=(), camera=(), microphone=()'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; worker-src 'self' blob:"
    if request.url.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    if config.PRODUCTION:response.headers['Strict-Transport-Security']='max-age=31536000'
    return response


class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email:str=Field(max_length=160)
    password:str=Field(max_length=128)


@app.get('/api/health')
def health():
    return {'status':'ok','application':'SmartMove','version':'1.0.0','synthetic':True}


@app.get('/api/auth/csrf')
def csrf(request:Request):
    token=secrets.token_urlsafe(32)
    response=JSONResponse({'csrf_token':token,'local_demo':not config.PRODUCTION})
    response.set_cookie('sm_csrf',token,httponly=True,secure=config.COOKIE_SECURE,samesite='strict',max_age=28800)
    session=request.cookies.get('sm_session')
    if session:
        with transaction() as con:con.execute('UPDATE sessions SET csrf_hash=? WHERE token_hash=?',(token_hash(token),token_hash(session)))
    return response


@app.post('/api/auth/login')
def login(data:Login,request:Request):
    rate_limit(request)
    email=data.email.strip().lower()
    with transaction() as con:
        user=row('SELECT * FROM users WHERE email=?',(email,),con)
        locked=user and user['locked_until'] and user['locked_until']>utcnow()
        good=False
        if user and not locked:
            try:good=HASHER.verify(user['password_hash'],data.password)
            except (VerificationError,InvalidHashError):pass
        if not user:
            __import__('hashlib').scrypt(data.password.encode(),salt=b'smartmove-timing-pad',n=16384,r=8,p=1)
        if not good or user['status']!='Active' or locked:
            if user:
                failures=user['failed_attempts']+1
                until=(datetime.now(timezone.utc)+timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ') if failures>=5 else None
                con.execute('UPDATE users SET failed_attempts=?,locked_until=? WHERE id=?',(failures,until,user['id']))
            audit(con,{'email':email},'login_failed','auth',request=request)
            con.commit()
            raise HTTPException(401,'Invalid credentials, inactive account or temporary lockout.')
        con.execute('UPDATE users SET failed_attempts=0,locked_until=NULL WHERE id=?',(user['id'],))
        if HASHER.check_needs_rehash(user['password_hash']):con.execute('UPDATE users SET password_hash=? WHERE id=?',(HASHER.hash(data.password),user['id']))
        session=secrets.token_urlsafe(48)
        expires=(datetime.now(timezone.utc)+timedelta(hours=8)).strftime('%Y-%m-%dT%H:%M:%SZ')
        con.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?)',(token_hash(session),user['id'],token_hash(request.headers['x-csrf-token']),user['auth_version'],utcnow(),expires,request.client.host if request.client else '',request.headers.get('user-agent','')[:250]))
        audit(con,user,'login','auth',request=request)
    response=JSONResponse({'user':public_user(user)})
    response.set_cookie('sm_session',session,httponly=True,secure=config.COOKIE_SECURE,samesite='strict',max_age=28800)
    return response


@app.get('/api/auth/me')
def me(request:Request):
    return {'user':public_user(current_user(request))}


@app.patch('/api/profile')
async def update_profile(request:Request):
    user=current_user(request);payload=await request.json()
    if not isinstance(payload,dict) or set(payload)-{'name','province'}:
        raise HTTPException(422,'Only your display name and passenger province may be changed here.')
    name=payload.get('name',user['name'])
    if not isinstance(name,str) or not 2<=len(name.strip())<=100:raise HTTPException(422,'Enter a display name of 2–100 characters.')
    name=name.strip()
    from .resources import PROVINCES
    if 'province' in payload and (not user['customer_id'] or payload['province'] not in PROVINCES):raise HTTPException(422,'Select a valid passenger province.')
    with transaction() as con:
        con.execute('UPDATE users SET name=? WHERE id=?',(name,user['id']))
        if user['customer_id']:
            con.execute('UPDATE customers SET name=? WHERE id=?',(name,user['customer_id']))
            if 'province' in payload:con.execute('UPDATE customers SET province=? WHERE id=?',(payload['province'],user['customer_id']))
        audit(con,user,'modify','profile',user['id'],before={'name':user['name']},after={'name':name,**({'province':payload['province']} if 'province' in payload else {})},request=request)
    return {'message':'Your profile was updated.','user':public_user(row('SELECT * FROM users WHERE id=?',(user['id'],)))}


@app.post('/api/auth/logout')
def logout(request:Request):
    user=current_user(request)
    with transaction() as con:
        con.execute('DELETE FROM sessions WHERE token_hash=?',(user['session_hash'],));audit(con,user,'logout','auth',request=request)
    response=JSONResponse({'message':'Signed out.'});response.delete_cookie('sm_session');response.delete_cookie('sm_csrf');return response


@app.post('/api/auth/register')
async def register(request:Request):
    rate_limit(request,'register',5,3600);p=await request.json()
    if not isinstance(p,dict) or set(p)-{'name','email','password','province'}:raise HTTPException(422,'Invalid registration fields.')
    if not all(isinstance(p.get(k),str) for k in ['name','email','password']):raise HTTPException(422)
    email=p['email'].strip().lower();name=p['name'].strip()
    if not 2<=len(name)<=100 or len(email)>160 or not __import__('re').fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise HTTPException(422,'Enter a valid name and email.')
    password_ok(p['password'])
    from .resources import PROVINCES
    if p.get('province') not in PROVINCES:raise HTTPException(422,'Select a province.')
    with transaction() as con:
        if row('SELECT id FROM users WHERE email=?',(email,),con):return {'message':'If eligible, an activation message was generated. In local mode, check data/outbox.'}
        c=row('SELECT id FROM customers WHERE email=?',(email,),con)
        if c:raise HTTPException(409,'This address belongs to an existing passenger record. Ask an administrator to link your account.')
        cur=con.execute('INSERT INTO customers(name,email,province,loyalty_tier,created_at) VALUES(?,?,?,?,?)',(name,email,p['province'],'Standard',utcnow()))
        uid=con.execute('INSERT INTO users(email,name,role,password_hash,status,customer_id,created_at) VALUES(?,?,?,?,?,?,?)',(email,name,'Customer',HASHER.hash(p['password']),'Pending',cur.lastrowid,utcnow())).lastrowid
        user=row('SELECT * FROM users WHERE id=?',(uid,),con);issue_account_token(con,user,'activation');audit(con,user,'register','users',uid,request=request)
    return {'message':'Activation message generated. Local demo: open the newest activation file in data/outbox and use its token below.'}


@app.post('/api/auth/recover')
async def recover(request:Request):
    rate_limit(request,'recover',6,3600);p=await request.json();email=str(p.get('email',''))[:160].strip().lower()
    with transaction() as con:
        user=row('SELECT * FROM users WHERE email=?',(email,),con)
        if user and user['status']=='Active':issue_account_token(con,user,'reset')
    return {'message':'If an active account exists, a recovery message was generated. Local demo: check data/outbox. No email is sent externally.'}


@app.post('/api/auth/activate')
async def activate(request:Request):
    rate_limit(request,'token',12,300);p=await request.json();token=str(p.get('token',''))
    with transaction() as con:
        t=row("SELECT * FROM account_tokens WHERE token_hash=? AND kind='activation' AND used=0 AND expires_at>?",(token_hash(token),utcnow()),con)
        if not t:raise HTTPException(400,'Invalid or expired activation token.')
        con.execute("UPDATE users SET status='Active' WHERE id=? AND status='Pending'",(t['user_id'],));con.execute('UPDATE account_tokens SET used=1 WHERE token_hash=?',(t['token_hash'],))
        audit(con,None,'activate','users',t['user_id'],request=request)
    return {'message':'Account activated. You can sign in.'}


@app.post('/api/auth/reset')
async def reset(request:Request):
    rate_limit(request,'token',12,300);p=await request.json();password=str(p.get('password',''));password_ok(password)
    with transaction() as con:
        t=row("SELECT * FROM account_tokens WHERE token_hash=? AND kind='reset' AND used=0 AND expires_at>?",(token_hash(str(p.get('token',''))),utcnow()),con)
        if not t:raise HTTPException(400,'Invalid or expired recovery token.')
        con.execute('UPDATE users SET password_hash=?,auth_version=auth_version+1,failed_attempts=0,locked_until=NULL WHERE id=?',(HASHER.hash(password),t['user_id']))
        con.execute('DELETE FROM sessions WHERE user_id=?',(t['user_id'],));con.execute('UPDATE account_tokens SET used=1 WHERE user_id=?',(t['user_id'],));audit(con,None,'password_reset','users',t['user_id'],request=request)
    return {'message':'Password updated. All previous sessions revoked.'}


@app.get('/api/admin/users')
def users(request:Request):
    require(request,'security')
    return rows('SELECT id,email,name,role,status,employee_id,customer_id,created_at FROM users ORDER BY id')


@app.post('/api/admin/users')
async def add_user(request:Request):
    user=require(request,'security','administer');p=await request.json()
    role=p.get('role');email=str(p.get('email','')).strip().lower();name=str(p.get('name','')).strip()
    if role not in ROLES or not 2<=len(name)<=100 or len(email)>160 or '@' not in email:raise HTTPException(422,'Invalid user fields.')
    employee=p.get('employee_id') or None;customer=p.get('customer_id') or None
    with transaction() as con:
        if role in ['Driver','Engineer'] and not row('SELECT id FROM employees WHERE id=? AND job=?',(employee,role),con):raise HTTPException(422,'Link the appropriate employee record.')
        if role=='Customer' and not row('SELECT id FROM customers WHERE id=?',(customer,),con):raise HTTPException(422,'Link a customer record.')
        uid=con.execute('INSERT INTO users(email,name,role,password_hash,status,employee_id,customer_id,created_at) VALUES(?,?,?,?,?,?,?,?)',(email,name,role,HASHER.hash(secrets.token_urlsafe(32)),'Active',employee,customer,utcnow())).lastrowid
        created=row('SELECT * FROM users WHERE id=?',(uid,),con);issue_account_token(con,created,'reset');audit(con,user,'create','users',uid,after={'email':email,'role':role},request=request)
    return {'id':uid,'message':'Account created. A local password-setup message is in data/outbox.'}


@app.patch('/api/admin/users/{uid}')
async def update_user(uid:int,request:Request):
    user=require(request,'security','administer');p=await request.json()
    if set(p)-{'name','role','status','confirm'} or not p.get('confirm'):raise HTTPException(422,'Confirm the account change.')
    with transaction() as con:
        before=row('SELECT * FROM users WHERE id=?',(uid,),con)
        if not before:raise HTTPException(404)
        role=p.get('role',before['role']);status=p.get('status',before['status']);name=p.get('name',before['name'])
        if role not in ROLES or status not in ['Active','Disabled','Pending'] or not isinstance(name,str) or not 2<=len(name)<=100:raise HTTPException(422)
        if uid==user['id'] and (role!='Admin' or status!='Active'):raise HTTPException(409,'You cannot remove your own administrator access.')
        if before['role']=='Admin' and (role!='Admin' or status!='Active') and scalar("SELECT COUNT(*) FROM users WHERE role='Admin' AND status='Active'",con=con)<=1:raise HTTPException(409,'Keep at least one active administrator.')
        if role in ['Driver','Engineer'] and not row('SELECT id FROM employees WHERE id=? AND job=?',(before['employee_id'],role),con):raise HTTPException(422,'This account is not linked to an appropriate employee. Create a correctly linked account.')
        if role=='Customer' and not before['customer_id']:raise HTTPException(422,'Customer accounts need a passenger record.')
        con.execute('UPDATE users SET name=?,role=?,status=?,auth_version=auth_version+1 WHERE id=?',(name,role,status,uid));con.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        audit(con,user,'modify','users',uid,before={k:before[k] for k in ['name','role','status']},after={'name':name,'role':role,'status':status},request=request)
    return {'message':'Account updated; existing sessions revoked.'}


@app.delete('/api/admin/users/{uid}')
def delete_user(uid:int,request:Request,confirm:bool=False):
    user=require(request,'security','administer')
    if not confirm:raise HTTPException(422,'Confirmation required.')
    if uid==user['id']:raise HTTPException(409,'Cannot delete your own administrator account.')
    with transaction() as con:
        before=row('SELECT * FROM users WHERE id=?',(uid,),con)
        if not before:raise HTTPException(404)
        if before['role']=='Admin' and scalar("SELECT COUNT(*) FROM users WHERE role='Admin' AND status='Active'",con=con)<=1:raise HTTPException(409,'Keep one active administrator.')
        if row('SELECT id FROM incidents WHERE reported_by=? LIMIT 1',(uid,),con):raise HTTPException(409,'This account is referenced by incident history. Deactivate it instead.')
        con.execute('DELETE FROM users WHERE id=?',(uid,));audit(con,user,'delete','users',uid,before={'email':before['email'],'role':before['role']},request=request)
    return {'message':'Account deleted; audit history retained.'}


@app.get('/api/admin/permissions')
def permissions(request:Request):
    require(request,'security');return {'roles':ROLES,'modules':MODULES,'actions':ACTIONS,'grants':rows('SELECT * FROM permissions ORDER BY role,module,action')}


@app.put('/api/admin/permissions/{role}')
async def set_permissions(role:str,request:Request):
    user=require(request,'security','administer');p=await request.json()
    if role not in ROLES or role=='Admin' or not isinstance(p.get('grants'),list) or len(p['grants'])>200 or not p.get('confirm'):raise HTTPException(422,'Invalid role or missing confirmation.')
    grants=p['grants']
    for g in grants:
        if not isinstance(g,dict) or g.get('module') not in MODULES or g.get('action') not in ACTIONS:raise HTTPException(422,'Unknown permission.')
    with transaction() as con:
        con.execute('DELETE FROM permissions WHERE role=?',(role,))
        con.executemany('INSERT OR IGNORE INTO permissions VALUES(?,?,?)',[(role,g['module'],g['action']) for g in grants]);audit(con,user,'permissions','roles',role,after={'grants':grants},request=request)
    return {'message':'Permissions updated. Ownership restrictions remain enforced.'}


@app.get('/api/admin/audit')
def logs(request:Request):
    require(request,'security');return rows('SELECT * FROM audit_log ORDER BY id DESC LIMIT 200')


@app.get('/api/notifications')
def notifications(request:Request):
    u=current_user(request)
    return rows('SELECT n.*,CASE WHEN nr.user_id IS NULL THEN 0 ELSE 1 END is_read FROM notifications n LEFT JOIN notification_reads nr ON nr.notification_id=n.id AND nr.user_id=? WHERE n.user_id=? OR (n.user_id IS NULL AND (n.role=? OR ?=\'Admin\')) ORDER BY n.id DESC LIMIT 50',(u['id'],u['id'],u['role'],u['role']))


@app.post('/api/notifications/{nid}/read')
def read_notification(nid:int,request:Request):
    u=current_user(request)
    with transaction() as con:
        n=row("SELECT id FROM notifications WHERE id=? AND (user_id=? OR (user_id IS NULL AND (role=? OR ?='Admin')))",(nid,u['id'],u['role'],u['role']),con)
        if not n:raise HTTPException(404)
        con.execute('INSERT OR IGNORE INTO notification_reads VALUES(?,?)',(nid,u['id']))
    return {'message':'Marked as read.'}


def do_job(identifier,kind):
    try:
        command=[sys.executable,'-m','analytics.pipeline' if kind=='models' else 'analytics.etl']
        completed=subprocess.run(command,cwd=config.ROOT,capture_output=True,text=True,timeout=900)
        if completed.returncode:raise RuntimeError(completed.stderr[-1500:])
        with transaction() as con:con.execute("UPDATE jobs SET status='Completed',message=?,finished_at=? WHERE id=?",('Artifacts refreshed.',utcnow(),identifier))
    except Exception as e:
        logger.exception('Analytics job failed')
        with transaction() as con:con.execute("UPDATE jobs SET status='Failed',message=?,finished_at=? WHERE id=?",('Job failed. Check server log and optional analytics dependencies.',utcnow(),identifier))


@app.post('/api/jobs/{kind}')
def start_job(kind:str,request:Request,background:BackgroundTasks):
    if kind not in ['etl','models']:raise HTTPException(404)
    u=require(request,'quality' if kind=='etl' else 'models','create')
    with transaction() as con:
        if row("SELECT id FROM jobs WHERE status='Running'",con=con):raise HTTPException(409,'An analytics job is already running.')
        identifier=con.execute("INSERT INTO jobs(kind,status,message,started_at) VALUES(?,'Running','Working',?)",(kind,utcnow())).lastrowid
        audit(con,u,'rebuild',kind,identifier,request=request)
    background.add_task(do_job,identifier,kind)
    return {'id':identifier,'message':'Background rebuild started. The existing snapshot remains available until each output is refreshed.'}


@app.get('/api/jobs')
def jobs(request:Request):
    u=current_user(request)
    if not any(allowed(u,m) for m in ['quality','models']):raise HTTPException(403)
    return rows('SELECT * FROM jobs ORDER BY id DESC LIMIT 12')


@app.post('/api/staging/fuel')
async def import_fuel(request:Request):
    u=require(request,'quality','create');p=await request.json();text=p.get('csv','')
    if not isinstance(text,str) or len(text)>1000000:raise HTTPException(422,'Use a CSV smaller than 1 MiB.')
    reader=csv.DictReader(io.StringIO(text))
    if reader.fieldnames!=['trip_id','fuel_liters']:raise HTTPException(422,'CSV columns must be exactly trip_id,fuel_liters.')
    records=list(reader)
    if len(records)>10000:raise HTTPException(422,'Maximum 10,000 staging rows.')
    target=config.DATA/'staging_fuel.csv';tmp=target.with_suffix('.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,target)
    with transaction() as con:audit(con,u,'import_staging','quality',after={'rows':len(records)},request=request)
    return {'message':'Staging file saved. Validation reports rejects; operational trip data is unchanged.','rows':len(records)}


@app.get('/api/openapi.json')
def protected_openapi(request:Request):
    require(request,'models');return app.openapi()


@app.get('/')
def index():return FileResponse(config.ROOT/'web/index.html')


@app.get('/favicon.ico')
def favicon():return Response(status_code=204)

app.mount('/static',StaticFiles(directory=config.ROOT/'web'),name='static')
