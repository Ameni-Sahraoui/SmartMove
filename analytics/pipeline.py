import argparse
import importlib.metadata
import json
import math
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.ensemble import RandomForestClassifier,IsolationForest,RandomForestRegressor
from sklearn.metrics import roc_auc_score,average_precision_score,precision_score,recall_score,f1_score,confusion_matrix,brier_score_loss,mean_absolute_error,mean_squared_error
from xgboost import XGBClassifier
from smartmove.config import DB,ARTIFACTS,EXPORTS,DATASET_VERSION
from .etl import write_json,run_etl


def metrics(y,p,threshold=.5):
    pred=p>=threshold
    return {'roc_auc':float(roc_auc_score(y,p)),'pr_auc':float(average_precision_score(y,p)), 'precision':float(precision_score(y,pred,zero_division=0)),'recall':float(recall_score(y,pred,zero_division=0)),'f1':float(f1_score(y,pred,zero_division=0)),'brier':float(brier_score_loss(y,p)), 'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist(),'n':len(y),'prevalence':float(np.mean(y)), 'threshold':threshold,'calibration':[{'predicted':float(np.mean(p[(p>=a)&(p<a+.1)])),'observed':float(np.mean(y[(p>=a)&(p<a+.1)])),'n':int(sum((p>=a)&(p<a+.1)))} for a in np.arange(0,1,.1) if sum((p>=a)&(p<a+.1))>0]}


def classification(df,features,target,datecol,horizon=0):
    data=df.dropna(subset=[target]).sort_values(datecol).reset_index(drop=True)
    dates=sorted(data[datecol].unique());cut1=dates[int(len(dates)*.60)];cut2=dates[int(len(dates)*.80)]
    times=pd.to_datetime(data[datecol]);
    train=(times<pd.Timestamp(cut1)-pd.Timedelta(days=horizon)).to_numpy()
    valid=((times>=pd.Timestamp(cut1))&(times<pd.Timestamp(cut2)-pd.Timedelta(days=horizon))).to_numpy()
    test=(times>=pd.Timestamp(cut2)).to_numpy()
    X=data[features];y=data[target].to_numpy().astype(int)
    candidates={
      'Logistic Regression':make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(max_iter=500,random_state=42)),
      'Random Forest':make_pipeline(SimpleImputer(strategy='median'),RandomForestClassifier(n_estimators=80,min_samples_leaf=20,max_depth=9,n_jobs=2,random_state=42)),
      'XGBoost':make_pipeline(SimpleImputer(strategy='median'),XGBClassifier(n_estimators=90,max_depth=3,learning_rate=.06,subsample=.85,colsample_bytree=.9,n_jobs=2,random_state=42,eval_metric='logloss'))}
    reports=[];trained={}
    for name,model in candidates.items():
        model.fit(X[train],y[train]);pv=model.predict_proba(X[valid])[:,1]
        threshold=max(np.arange(.15,.76,.05),key=lambda t:f1_score(y[valid],pv>=t,zero_division=0))
        reports.append({'model':name,'validation_pr_auc':float(average_precision_score(y[valid],pv)),'test':metrics(y[test],model.predict_proba(X[test])[:,1],float(threshold))})
        trained[name]=model
    selected=max(reports,key=lambda x:x['validation_pr_auc']);name=selected['model']
    cv=[];available_dates=sorted(data.loc[train,datecol].unique())
    for frac in [.50,.65,.80]:
        left=available_dates[int(len(available_dates)*frac)];right=available_dates[min(len(available_dates)-1,int(len(available_dates)*(frac+.15)))]
        a=(times<pd.Timestamp(left)-pd.Timedelta(days=horizon)).to_numpy()
        b=((times>=pd.Timestamp(left))&(times<pd.Timestamp(right))).to_numpy()
        model=clone(candidates[name]).fit(X[a],y[a]);p=model.predict_proba(X[b])[:,1]
        cv.append({'train_end':str(left),'test_end':str(right),'pr_auc':float(average_precision_score(y[b],p)),'n':int(sum(b))})
    final=clone(candidates[name]).fit(X,y)
    return final,{'selected':name,'selection':'Highest validation PR-AUC; threshold selected on validation F1 only. Test labels were not used for selection.','features':features,'label':target,'models':reports,'chronological_cv':cv,'train_before':str(cut1),'test_from':str(cut2),'purge_days':horizon,'counts':{'train':int(sum(train)),'validation':int(sum(valid)),'test':int(sum(test))},'threshold':selected['test']['threshold'],'limits':'Results measure a synthetic generator, not field performance. Probabilities are model outputs, not guaranteed outcomes. Validate and calibrate on representative operational data before use.'}


def forecast_design(dates,origin):
    dt=pd.DatetimeIndex(dates);t=(dt-pd.Timestamp(origin)).days.to_numpy()
    return np.column_stack([t/365,np.sin(2*np.pi*t/365.25),np.cos(2*np.pi*t/365.25)]+[(dt.dayofweek==i).astype(float) for i in range(7)])


def forecasting(con,asof):
    df=pd.read_sql_query("SELECT route_id,substr(departure_utc,1,10) date,SUM(passenger_count) passengers FROM trips WHERE status='Completed' GROUP BY route_id,date",con)
    routes=pd.read_sql_query('SELECT id,name FROM routes',con)
    all_dates=pd.date_range(df['date'].min(),asof);future=pd.date_range(pd.Timestamp(asof)+pd.Timedelta(days=1),periods=180)
    output=[];scores=[];historical=[]
    for rt in routes.itertuples():
        d=df[df.route_id==rt.id].set_index('date')['passengers'];d.index=pd.to_datetime(d.index);y=d.reindex(all_dates,fill_value=0).to_numpy()
        X=forecast_design(all_dates,all_dates[0]);n=len(y)
        ridge=Ridge(alpha=12).fit(X[:-56],y[:-56]);pv=np.maximum(0,ridge.predict(X[-56:-28]))
        medians={i:float(np.mean(y[:-56][all_dates[:-56].dayofweek==i][-8:])) for i in range(7)}
        bv=np.array([medians[i] for i in all_dates[-56:-28].dayofweek])
        choose_ridge=mean_absolute_error(y[-56:-28],pv)<=mean_absolute_error(y[-56:-28],bv)
        if choose_ridge:
            test_model=Ridge(alpha=12).fit(X[:-28],y[:-28]);pred=np.maximum(0,test_model.predict(X[-28:]));final=Ridge(alpha=12).fit(X,y);pf=np.maximum(0,final.predict(forecast_design(future,all_dates[0])))
            resid=np.abs(y[-56:-28]-pv)
        else:
            medians={i:float(np.mean(y[:-28][all_dates[:-28].dayofweek==i][-8:])) for i in range(7)};pred=np.array([medians[i] for i in all_dates[-28:].dayofweek]);
            medians={i:float(np.mean(y[all_dates.dayofweek==i][-8:])) for i in range(7)};pf=np.array([medians[i] for i in future.dayofweek]);resid=np.abs(y[-56:-28]-bv)
        band=float(np.quantile(resid,min(1,math.ceil((len(resid)+1)*.8)/len(resid)),method='higher'))
        scores.append({'route_id':rt.id,'route':rt.name,'model':'Calendar Ridge' if choose_ridge else 'Weekday trailing-8 mean','mae':float(mean_absolute_error(y[-28:],pred)),'rmse':float(np.sqrt(mean_squared_error(y[-28:],pred))),'band_coverage_28d':float(np.mean(np.abs(y[-28:]-pred)<=band)),'test_days':28,'calibration_days':28})
        for dt,actual in zip(all_dates[-180:],y[-180:]):historical.append({'date':dt.strftime('%Y-%m-%d'),'route_id':rt.id,'actual':int(actual)})
        for dt,p in zip(future,pf):output.append({'date':dt.strftime('%Y-%m-%d'),'route_id':rt.id,'forecast':round(float(p),2),'lower':round(max(0,float(p)-band),2),'upper':round(float(p)+band,2)})
    return {'daily':output,'actual':historical,'evaluation':scores,'as_of':asof,'band_note':'80% empirical absolute-residual band calibrated on a 28-day validation window. Coverage is reported on the 28-day holdout; 180-day extrapolation is not calibrated. Aggregated bounds sum route-level bounds and are not a joint confidence interval.','selection':'Calendar Ridge vs weekday trailing-8 mean, selected by validation MAE, then evaluated on a separate last-28-day holdout.'}


def run():
    print('ETL and quality validation',flush=True);run_etl()
    con=sqlite3.connect(DB)
    asof=con.execute("SELECT value FROM meta WHERE key='as_of'").fetchone()[0]
    telem=pd.read_sql_query('SELECT t.*,v.code,v.type,v.facility_id FROM telemetry t JOIN vehicles v ON v.id=t.vehicle_id',con)
    mf=['engine_temp','brake_wear','battery_voltage','km_since_service','vibration']
    print('Training maintenance classifiers',flush=True)
    model,mreport=classification(telem,mf,'fault_7d','captured_at',7)
    latest=telem.sort_values('captured_at').groupby('vehicle_id').tail(1).copy()
    latest['probability']=model.predict_proba(latest[mf])[:,1]
    iso=IsolationForest(n_estimators=60,contamination=.05,random_state=42,n_jobs=2).fit(telem.loc[telem.fault_7d.notna(),mf])
    latest['anomaly']=iso.predict(latest[mf])==-1
    explanation_status='SHAP not available';global_shap=[];values=None
    try:
        import shap
        transformed=model[:-1].transform(latest[mf]);est=model[-1]
        if isinstance(est,LogisticRegression):
            explainer=shap.LinearExplainer(est,model[:-1].transform(telem.loc[telem.fault_7d.notna(),mf].sample(min(250,len(telem.dropna())),random_state=42)))
            sv=explainer.shap_values(transformed);unit='log-odds'
        else:
            explainer=shap.TreeExplainer(est);sv=explainer.shap_values(transformed);unit='probability' if isinstance(est,RandomForestClassifier) else 'log-odds'
        values=np.asarray(sv)
        if values.ndim==3: values=values[:,:,1]
        base=np.asarray(explainer.expected_value).flatten();base=float(base[-1])
        reconstructed=base+values.sum(axis=1)
        if unit=='log-odds':reconstructed=1/(1+np.exp(-reconstructed))
        residual=float(np.max(np.abs(reconstructed-latest.probability.to_numpy())))
        explanation_status=f'SHAP computed; contributions in {unit}; max reconstruction residual {residual:.8f}'
        global_shap=[{'feature':f,'mean_abs_shap':float(np.mean(np.abs(values[:,j])))} for j,f in enumerate(mf)]
        mreport['shap']={'status':explanation_status,'global':global_shap,'units':unit,'base_value':base,'max_reconstruction_residual':residual}
    except ImportError:
        mreport['shap']={'status':'SHAP dependency unavailable; no SHAP values fabricated.','global':[]}
    risks=[]
    for idx,x in enumerate(latest.to_dict('records')):
        if values is not None:
            x['explanation']=[{'feature':f,'value':float(x[f]),'contribution':float(values[idx,j])} for j,f in enumerate(mf)]
        x.pop('fault_7d',None);x['risk_score']=round(x['probability']*100);x['risk_level']='High' if x['probability']>=.6 else 'Moderate' if x['probability']>=.35 else 'Low'
        if x['engine_temp']>98:x['issue']='Elevated engine temperature'
        elif x['brake_wear']>62:x['issue']='Brake-wear trend'
        elif x['battery_voltage']<12:x['issue']='Low battery voltage'
        elif x['km_since_service']>11000:x['issue']='Service interval review'
        else:x['issue']='Combined telemetry pattern'
        risks.append(x)
    write_json(ARTIFACTS/'maintenance.json',{'records':risks,'model':mreport,'explanation_notice':'SHAP explains the model, not physical causation. Engineers must assess the vehicle; this is not a safety certification.'})
    trips=pd.read_sql_query('SELECT t.*,r.distance_km,r.duration_min,r.name route FROM trips t JOIN routes r ON r.id=t.route_id',con)
    dt=pd.to_datetime(trips.departure_utc);trips['date']=dt.dt.strftime('%Y-%m-%d');trips['weekday']=dt.dt.dayofweek;trips['month']=dt.dt.month;trips['late']=(trips.delay_min>15).astype(int)
    df=['distance_km','duration_min','weather_index','congestion_index','peak_hour','weekday','month']
    print('Training delay classifiers',flush=True)
    dm,dreport=classification(trips[trips.status=='Completed'],df,'late','date')
    future=trips[trips.status.isin(['Scheduled','In progress'])].copy();future['probability']=dm.predict_proba(future[df])[:,1]
    write_json(ARTIFACTS/'delay.json',{'records':future[['id','code','route_id','route','departure_utc','probability','weather_index','congestion_index']].to_dict('records'),'model':dreport,'notice':'Probability of >15 minutes delay. Weather and congestion indices are synthetic pre-departure inputs, not live external feeds.'})
    print('Demand forecasts',flush=True);fr=forecasting(con,asof);write_json(ARTIFACTS/'forecast.json',fr)
    done=trips[trips.status=='Completed'].sort_values('date').copy();cut=int(len(done)*.8)
    regr=RandomForestRegressor(n_estimators=60,min_samples_leaf=25,max_depth=9,n_jobs=2,random_state=42)
    rf=df+['capacity'];y=(done.revenue_cents-done.operating_cost_cents)/100
    regr.fit(done[rf].iloc[:cut],y.iloc[:cut]);pred=regr.predict(done[rf].iloc[cut:])
    rreport={'model':'Random Forest Regressor','target':'Trip contribution (CAD), before central overhead','mae_cad':float(mean_absolute_error(y.iloc[cut:],pred)),'baseline_mae_cad':float(mean_absolute_error(y.iloc[cut:],np.full(len(y)-cut,float(y.iloc[:cut].mean())))),'test_n':len(y)-cut,'split':'Chronological 80/20; no final refit affects the reported holdout metric.','limitation':'Synthetic revenue and cost assumptions. Not audited accounting or a causal profitability estimate.'}
    model_report={'trained_at':datetime.now(timezone.utc).isoformat(),'dataset_version':DATASET_VERSION,'as_of':asof,'model_version':'smartmove-ml-v1','maintenance':mreport,'delay':dreport,'route_performance':rreport,'forecast':{'mean_route_mae':float(np.mean([x['mae'] for x in fr['evaluation']])),'mean_band_coverage':float(np.mean([x['band_coverage_28d'] for x in fr['evaluation']])),'routes':len(fr['evaluation']),'details':fr['selection']},'versions':{m:importlib.metadata.version(m) for m in ['numpy','pandas','scikit-learn','xgboost','scipy']},'deployment_note':'Models are reproducible from source. Serving uses bundled prediction snapshots; rerun this pipeline after operational data changes. No untrusted pickle files are loaded.'}
    write_json(ARTIFACTS/'models.json',model_report)
    pd.DataFrame(fr['daily']).to_csv(EXPORTS/'fact_demand_forecast.csv',index=False)
    pd.DataFrame([{k:v for k,v in x.items() if k!='explanation'} for x in risks]).to_csv(EXPORTS/'fact_vehicle_risk.csv',index=False)
    future[['id','route_id','departure_utc','probability']].to_csv(EXPORTS/'fact_delay_risk.csv',index=False)
    con.close();print('Analytics complete.',flush=True)


if __name__=='__main__':run()
