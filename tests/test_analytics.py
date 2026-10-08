import json
from pathlib import Path
from smartmove.config import ARTIFACTS,DB
from analytics.etl import quality
from analytics.optimize import allocate


def test_data_integrity():
    q=quality(DB);assert q['critical_pass'],q['checks']


def test_probability_bounds():
    for name in ['maintenance','delay']:
        d=json.loads((ARTIFACTS/f'{name}.json').read_text())
        assert all(0<=r['probability']<=1 for r in d['records'])


def test_shap_reconstructs_prediction():
    d=json.loads((ARTIFACTS/'maintenance.json').read_text())
    assert d['model']['shap']['max_reconstruction_residual']<1e-5


def test_holdout_is_after_training():
    d=json.loads((ARTIFACTS/'models.json').read_text())
    for key in ['maintenance','delay']:
        r=d[key];assert r['train_before']<r['test_from']
        assert all(x['test']['n']==r['counts']['test'] for x in r['models'])
        assert all(0<=x['test']['pr_auc']<=1 and 0<=x['test']['brier']<=1 for x in r['models'])


def test_optimizer_constraints():
    routes=[{'id':1,'name':'R1','distance_km':200,'duration_min':150,'demand':40},{'id':2,'name':'R2','distance_km':200,'duration_min':600,'demand':25}]
    vehicles=[{'id':1,'code':'V1','capacity':50},{'id':2,'code':'V2','capacity':50}]
    r=allocate(routes,vehicles,1)
    assert len(r['allocations'])<=1
    assert all(x['route_id']!=2 for x in r['allocations'])
    assert r['unserved']>=25


def test_optimizer_without_optional_solver():
    r=allocate([{'id':1,'name':'R1','duration_min':100,'distance_km':80,'demand':65}],[{'id':1,'code':'V1','capacity':50}],1,use_milp=False)
    assert r['unserved']==15 and r['optimal'] is False
