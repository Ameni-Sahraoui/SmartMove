import secrets
import sqlite3
import pytest
from smartmove.database import connect,rows,scalar
from smartmove import config


def test_health(client):
    r=client.get('/api/health');assert r.status_code==200 and r.json()['synthetic']


def test_anonymous_dashboard_blocked(client):
    assert client.get('/api/dashboard').status_code==401


def test_bad_password_is_rejected(client):
    assert client.post('/api/auth/login',json={'email':'admin@smartmove.example','password':'bad'}).status_code==401


def test_missing_csrf_rejected(client):
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/auth/login',json={'email':'admin@smartmove.example','password':'anything'}).status_code==403


def test_cross_origin_write_rejected(client):
    assert client.post('/api/auth/login',json={'email':'admin@smartmove.example','password':'anything'},headers={'Origin':'https://evil.example'}).status_code==403


def test_admin_sees_all_permissions(login):
    c=login('Admin');p=c.get('/api/auth/me').json()['user']['permissions'];assert 'administer' in p['security']


def test_http_only_session(login):
    c=login('Admin');assert c.cookies.get('sm_session');assert not c.get('/api/auth/me').json().get('password_hash')


def test_driver_cannot_access_admin(login):
    c=login('Driver');assert c.get('/api/admin/users').status_code==403


def test_driver_cannot_read_finances(login):
    c=login('Driver');assert c.get('/api/dashboard').status_code==403;assert c.get('/api/resources/payments').status_code==403


def test_driver_only_owns_assigned_trips(login):
    c=login('Driver');d=c.get('/api/resources/trips').json();assert d['items'];assert all(x['driver_id']==1 for x in d['items'])


def test_driver_cannot_edit_other_trip(login):
    c=login('Driver');tid=scalar('SELECT id FROM trips WHERE driver_id<>1 LIMIT 1')
    assert c.patch(f'/api/resources/trips/{tid}',json={'status':'In progress'}).status_code==404


def test_driver_cannot_change_vehicle(login):
    c=login('Driver');tid=scalar('SELECT id FROM trips WHERE driver_id=1 LIMIT 1')
    assert c.patch(f'/api/resources/trips/{tid}',json={'vehicle_id':2}).status_code==403


def test_customer_reservations_are_private(login):
    c=login('Customer');d=c.get('/api/resources/reservations').json();assert d['items'];assert all(x['customer_id']==1 for x in d['items'])


def test_customer_cannot_access_another_ticket(login):
    c=login('Customer');rid=scalar('SELECT id FROM reservations WHERE customer_id<>1 LIMIT 1')
    assert c.get(f'/api/reservations/{rid}/ticket').status_code==404


def test_customer_trips_hide_internal_costs(login):
    c=login('Customer');d=c.get('/api/resources/trips').json();assert d['items'];assert all('operating_cost_cents' not in x and 'driver_id' not in x for x in d['items'])


def test_booking_and_cancellation_reconcile(login):
    c=login('Customer');tid=scalar("SELECT id FROM trips WHERE status='Scheduled' AND capacity-passenger_count>=2 LIMIT 1")
    before=scalar('SELECT passenger_count FROM trips WHERE id=?',(tid,))
    r=c.post('/api/resources/reservations',json={'trip_id':tid,'seats':2,'customer_id':999});assert r.status_code==200,r.text
    rid=r.json()['id'];assert scalar('SELECT customer_id FROM reservations WHERE id=?',(rid,))==1
    assert scalar('SELECT passenger_count FROM trips WHERE id=?',(tid,))==before+2
    assert c.get(f'/api/reservations/{rid}/ticket').status_code==200
    assert c.post(f'/api/reservations/{rid}/cancel').status_code==200
    assert scalar('SELECT passenger_count FROM trips WHERE id=?',(tid,))==before
    assert scalar('SELECT status FROM payments WHERE reservation_id=?',(rid,))=='Simulated refund'
    assert c.post(f'/api/reservations/{rid}/cancel').status_code==409


def test_overselling_is_blocked(login):
    c=login('Customer');tid=scalar("SELECT id FROM trips WHERE status='Scheduled' AND capacity-passenger_count<8 LIMIT 1")
    assert c.post('/api/resources/reservations',json={'trip_id':tid,'seats':8}).status_code==409


def test_analyst_cannot_edit_fleet(login):
    c=login('Analyst');assert c.patch('/api/resources/fleet/1',json={'status':'Standby'}).status_code==403


def test_engineer_cannot_read_customer_reservations(login):
    c=login('Engineer');assert c.get('/api/resources/reservations').status_code==403


def test_invalid_vehicle_capacity(login):
    c=login('Admin');assert c.patch('/api/resources/fleet/1',json={'capacity':-4}).status_code==422


def test_unknown_field_cannot_change_protected_state(login):
    c=login('Admin');assert c.patch('/api/resources/fleet/1',json={'password_hash':'x'}).status_code==422


def test_route_origin_destination_validation(login):
    c=login('Admin');assert c.post('/api/resources/routes',json={'name':'Invalid route','origin_id':1,'destination_id':1,'distance_km':20,'duration_min':60,'fare_cents':100,'status':'Active'}).status_code==422


def test_sql_injection_search_remains_data(login):
    c=login('Admin');r=c.get('/api/resources/routes',params={'q':"'; DROP TABLE users; --"});assert r.status_code==200;assert scalar('SELECT COUNT(*) FROM users')>=6


def test_unknown_resource_is_not_queryable(login):
    c=login('Admin');assert c.get('/api/resources/users').status_code==404


def test_account_self_lockout_is_blocked(login):
    c=login('Admin');uid=c.get('/api/auth/me').json()['user']['id']
    assert c.patch(f'/api/admin/users/{uid}',json={'status':'Disabled','confirm':True}).status_code==409
    assert c.delete(f'/api/admin/users/{uid}?confirm=true').status_code==409


def test_account_deactivation_revokes_session(login):
    from fastapi.testclient import TestClient
    from smartmove.app import app
    from tests.conftest import PASSWORD
    c=login('Admin');uid=scalar("SELECT id FROM users WHERE role='Manager' LIMIT 1")
    with TestClient(app) as m:
        token=m.get('/api/auth/csrf').json()['csrf_token'];m.headers['X-CSRF-Token']=token
        assert m.post('/api/auth/login',json={'email':'manager@smartmove.example','password':PASSWORD}).status_code==200
        assert c.patch(f'/api/admin/users/{uid}',json={'status':'Disabled','confirm':True}).status_code==200
        assert m.get('/api/dashboard').status_code==401
    assert c.patch(f'/api/admin/users/{uid}',json={'status':'Active','confirm':True}).status_code==200


def test_dashboard_metrics_equal_database(login):
    c=login('Admin');d=c.get('/api/dashboard?days=30').json();values={m['key']:m['value'] for m in d['metrics']}
    actual=scalar("SELECT COUNT(*) FROM trips WHERE departure_utc>='2026-08-02' AND departure_utc<'2026-09-01'")
    assert values['total_trips']==actual;assert len(d['metrics'])==8;assert len(d['recommendations'])==3


def test_forecast_bounds_and_daily_aggregation(login):
    c=login('Analyst');d=c.get('/api/analytics/forecast?grain=day&horizon=30').json()
    future=[x for x in d['points'] if x['forecast'] is not None];assert len(future)==30
    assert all(0<=x['lower']<=x['forecast']<=x['upper'] for x in future)


def test_what_if_is_neutral_at_zero(login):
    c=login('Admin');d=c.post('/api/simulate',json={}).json();assert abs(d['baseline']['occupancy']-d['scenario']['occupancy'])<1e-9;assert d['baseline']['delay']==d['scenario']['delay']


def test_what_if_range_guard(login):
    c=login('Admin');assert c.post('/api/simulate',json={'capacity_change':-101}).status_code==422


def test_staging_never_overwrites_operations(login):
    c=login('Analyst');before=scalar('SELECT fuel_liters FROM trips WHERE id=1')
    r=c.post('/api/staging/fuel',json={'csv':'trip_id,fuel_liters\n1,-400\n999999,40\n1,25\n'});assert r.status_code==200
    assert scalar('SELECT fuel_liters FROM trips WHERE id=1')==before


def test_admin_audit_excludes_secrets(login):
    c=login('Admin');text=c.get('/api/admin/audit').text;assert 'password_hash' not in text and 'csrf_hash' not in text


def test_logout_invalidates_cookie(login):
    c=login('Admin');assert c.post('/api/auth/logout').status_code==200;assert c.get('/api/auth/me').status_code==401


def test_password_reset_token_is_one_time(client):
    from smartmove.security import HASHER,token_hash
    from datetime import datetime,timedelta,timezone
    token=secrets.token_urlsafe(32)
    with connect() as con:
        uid=con.execute("INSERT INTO users(email,name,role,password_hash,status,created_at) VALUES(?,?,'Analyst',?,'Active',?)",('reset-'+secrets.token_hex(4)+'@example.test','Reset Test',HASHER.hash('TempPassword9912'),datetime.now(timezone.utc).isoformat())).lastrowid
        con.execute("INSERT INTO account_tokens VALUES(?,?,'reset',?,0)",(token_hash(token),uid,(datetime.now(timezone.utc)+timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')))
    p={'token':token,'password':'New-test-password-1425'}
    assert client.post('/api/auth/reset',json=p).status_code==200
    assert client.post('/api/auth/reset',json=p).status_code==400


def test_response_security_headers(client):
    r=client.get('/');assert r.headers['X-Content-Type-Options']=='nosniff';assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']


def test_no_secret_download(client):
    assert client.get('/static/../data/LOCAL_CREDENTIALS.txt').status_code==404
    assert client.get('/data/LOCAL_CREDENTIALS.txt').status_code==404


def test_profile_cannot_escalate_role(login):
    c=login('Customer')
    assert c.patch('/api/profile',json={'role':'Admin'}).status_code==422
    assert c.get('/api/auth/me').json()['user']['role']=='Customer'


def test_profile_updates_only_self(login):
    c=login('Customer');before=c.get('/api/auth/me').json()['user']
    r=c.patch('/api/profile',json={'name':'Passenger Updated'})
    assert r.status_code==200 and r.json()['user']['name']=='Passenger Updated'
    assert r.json()['user']['id']==before['id']
    assert c.patch('/api/profile',json={'name':before['name']}).status_code==200


def test_invalid_content_length(client):
    assert client.post('/api/auth/login',content='{}',headers={'Content-Length':'invalid'}).status_code==400
