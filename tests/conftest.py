import os
import shutil
import tempfile
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
TEST_DIR=Path(tempfile.mkdtemp(prefix='smartmove-tests-'))
shutil.copy(ROOT/'data/smartmove.db',TEST_DIR/'smartmove.db')
shutil.copy(ROOT/'data/staging_fuel.csv',TEST_DIR/'staging_fuel.csv')
os.environ['SMARTMOVE_DATA_DIR']=str(TEST_DIR)
os.environ['SMARTMOVE_ARTIFACTS_DIR']=str(ROOT/'artifacts')
os.environ['SMARTMOVE_EXPORTS_DIR']=str(ROOT/'exports')

from fastapi.testclient import TestClient
from smartmove.app import app
from smartmove.database import connect
from smartmove.security import HASHER,RATE

PASSWORD='Test-only-'+__import__('secrets').token_urlsafe(14)+'7'


@pytest.fixture(scope='session',autouse=True)
def initialize():
    with TestClient(app):pass
    with connect() as con:
        con.execute('UPDATE users SET password_hash=?,failed_attempts=0,locked_until=NULL',(HASHER.hash(PASSWORD),))
        con.execute('DELETE FROM sessions')
    yield
    shutil.rmtree(TEST_DIR,ignore_errors=True)


@pytest.fixture
def client():
    RATE.clear()
    with TestClient(app) as c:
        token=c.get('/api/auth/csrf').json()['csrf_token'];c.headers['X-CSRF-Token']=token
        yield c


@pytest.fixture
def login(client):
    def as_role(role):
        token=client.get('/api/auth/csrf').json()['csrf_token'];client.headers['X-CSRF-Token']=token
        response=client.post('/api/auth/login',json={'email':role.lower()+'@smartmove.example','password':PASSWORD})
        assert response.status_code==200,response.text
        return client
    return as_role
