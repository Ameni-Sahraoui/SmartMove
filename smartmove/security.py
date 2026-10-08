import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from . import config
from .database import audit, connect, row, rows, transaction, utcnow

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
ROLES = ("Admin", "Manager", "Driver", "Engineer", "Analyst", "Customer")
MODULES = ("overview","operations","fleet","routes","facilities","employees","trips","reservations","payments","maintenance","parts","demand","predictive","delay","experience","simulation","quality","security","models","documents","incidents","complaints","notifications","profile")
ACTIONS = ("view","create","modify","delete","approve","export","administer")
DEFAULTS = {
    "Manager": {m: ["view","export"] for m in ("overview","operations","fleet","routes","facilities","employees","trips","reservations","payments","maintenance","demand","predictive","delay","experience","simulation","models","documents","incidents","complaints")},
    "Analyst": {m: ["view","export"] for m in ("overview","operations","fleet","routes","facilities","trips","demand","predictive","delay","experience","simulation","quality","models","documents")},
    "Engineer": {m:["view"] for m in ("fleet","maintenance","parts","predictive","documents")},
    "Driver": {"trips":["view","modify"],"incidents":["view","create"],"documents":["view"]},
    "Customer": {"routes":["view"],"trips":["view"],"reservations":["view","create","modify"],"complaints":["view","create"],"payments":["view"]},
}
for m in ("trips","reservations","incidents","maintenance","routes","fleet","complaints"):
    DEFAULTS["Manager"][m] += ["create","modify"]
for m in ("maintenance","parts"):
    DEFAULTS["Engineer"][m] += ["create","modify"]
DEFAULTS["Analyst"]["quality"] += ["create"]
DEFAULTS["Analyst"]["models"] += ["create"]
for r in DEFAULTS:
    DEFAULTS[r]["notifications"]=["view","modify"]
    DEFAULTS[r]["profile"]=["view","modify"]
RATE = defaultdict(deque)
RATE_LOCK = Lock()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_ok(password):
    if len(password)<12 or len(password)>128 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(422,"Use a password of 12–128 characters including a letter and a number.")


def rate_limit(request, bucket="auth", limit=12, seconds=300):
    key=(request.client.host if request.client else "local",bucket)
    now=time.monotonic()
    with RATE_LOCK:
        q=RATE[key]
        while q and q[0]<now-seconds:
            q.popleft()
        if len(q)>=limit:
            raise HTTPException(429,"Too many attempts. Wait five minutes before trying again.")
        q.append(now)
        if len(RATE)>5000:
            for k in list(RATE):
                if not RATE[k] or RATE[k][-1]<now-seconds:
                    RATE.pop(k,None)


def bootstrap():
    with transaction() as con:
        if not con.execute("SELECT 1 FROM permissions LIMIT 1").fetchone():
            con.executemany("INSERT INTO permissions VALUES(?,?,?)",[(r,m,a) for r,p in DEFAULTS.items() for m,aa in p.items() for a in aa])
        if con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return
        if config.PRODUCTION:
            email=__import__('os').environ.get('SMARTMOVE_ADMIN_EMAIL','')
            password=__import__('os').environ.get('SMARTMOVE_ADMIN_PASSWORD','')
            if not email or not password:
                raise RuntimeError("Production bootstrap needs SMARTMOVE_ADMIN_EMAIL and SMARTMOVE_ADMIN_PASSWORD.")
            password_ok(password)
            con.execute("INSERT INTO users(email,name,role,password_hash,status,created_at) VALUES(?,?,?,?,?,?)",(email.lower(),"Administrator","Admin",HASHER.hash(password),"Active",utcnow()))
            return
        lines=["SMARTMOVE • LOCAL SYNTHETIC DEMO ACCOUNTS", "Generated on this computer. Keep this file private. Not production credentials.", ""]
        for role,name,employee,customer in [("Admin","Jordan Davis",None,None),("Manager","Morgan Lee",None,None),("Driver","Driver 001",1,None),("Engineer","Engineer 01",161,None),("Analyst","Ameni • BI Analyst",None,None),("Customer","Passenger 00001",None,1)]:
            email=role.lower()+"@smartmove.example"
            password=secrets.token_urlsafe(14)+"9a"
            con.execute("INSERT INTO users(email,name,role,password_hash,status,employee_id,customer_id,created_at) VALUES(?,?,?,?,?,?,?,?)",(email,name,role,HASHER.hash(password),"Active",employee,customer,utcnow()))
            lines.append(f"{role:9}  {email:29}  {password}")
        credentials=config.DATA/"LOCAL_CREDENTIALS.txt"
        credentials.write_text("\n".join(lines)+"\n",encoding="utf-8")
        try: credentials.chmod(0o600)
        except OSError: pass
        print(f"\nLocal sign-in credentials: {credentials}\n",flush=True)


def current_user(request:Request):
    cookie=request.cookies.get("sm_session","")
    if not cookie:
        raise HTTPException(401,"Sign in to SmartMove.")
    user=row("SELECT u.*,s.token_hash AS session_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND s.auth_version=u.auth_version AND u.status='Active'",(token_hash(cookie),utcnow()))
    if not user:
        raise HTTPException(401,"Your session expired or was revoked. Sign in again.")
    return user


def allowed(user,module,action="view"):
    if user["role"]=="Admin":
        return True
    return bool(row("SELECT 1 FROM permissions WHERE role=? AND module=? AND action=?",(user["role"],module,action)))


def require(request,module,action="view"):
    user=current_user(request)
    if not allowed(user,module,action):
        raise HTTPException(403,"Your role is not authorized for this operation.")
    return user


def public_user(user):
    permissions={m:list(ACTIONS) for m in MODULES} if user["role"]=="Admin" else {}
    if user["role"]!="Admin":
        for p in rows("SELECT module,action FROM permissions WHERE role=?",(user["role"],)):
            permissions.setdefault(p["module"],[]).append(p["action"])
    return {k:user[k] for k in ("id","name","email","role","employee_id","customer_id")} | {"permissions":permissions}


def csrf_check(request):
    origin=request.headers.get("origin")
    if origin and (urlparse(origin).netloc!=request.headers.get("host") or urlparse(origin).scheme!=request.url.scheme):
        raise HTTPException(403,"Cross-origin write rejected.")
    cookie=request.cookies.get("sm_csrf","")
    header=request.headers.get("x-csrf-token","")
    if not cookie or not header or not secrets.compare_digest(cookie,header):
        raise HTTPException(403,"Security token missing or expired. Refresh the page.")
    if request.cookies.get("sm_session"):
        s=row("SELECT csrf_hash FROM sessions WHERE token_hash=?",(token_hash(request.cookies["sm_session"]),))
        if s and not secrets.compare_digest(s["csrf_hash"],token_hash(header)):
            raise HTTPException(403,"Session security token changed. Refresh the page.")


def issue_account_token(con,user,kind):
    token=secrets.token_urlsafe(32)
    expires=(datetime.now(timezone.utc)+timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    con.execute("UPDATE account_tokens SET used=1 WHERE user_id=? AND kind=?",(user['id'],kind))
    con.execute("INSERT INTO account_tokens VALUES(?,?,?,?,0)",(token_hash(token),user['id'],kind,expires))
    if config.PRODUCTION:
        raise HTTPException(503,"Email delivery is not configured. Account-token delivery must be implemented before production use.")
    outbox=config.DATA/"outbox";outbox.mkdir(exist_ok=True)
    f=outbox/f"{kind}-{user['id']}-{secrets.token_hex(4)}.txt"
    f.write_text(f"LOCAL MAIL SIMULATOR — never publish this file\nTo: {user['email']}\nPurpose: {kind}\nExpires: {expires}\nToken: {token}\nPaste this token into SmartMove's account recovery form.\n",encoding="utf-8")
    try: f.chmod(0o600)
    except OSError: pass
