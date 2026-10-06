import json,time
from app.services.ml_v2.registry import run_feature
from app.services.ml_v2.core.data_loader import available_symbols,data_inventory
symbols=[s for s in ['AAPL','MSFT','SPY','AMZN','GOOGL','META','NVDA','JPM'] if s in available_symbols()]
print('selected',symbols,flush=True)
results=[]
for feature in [1,2,3,4,5,6,8]:
    p={'symbols':symbols,'max_symbols':8,'lookback_days':756}
    p.update({1:{'model_type':'ridge','cpcv_n_groups':4},2:{'model_family':'ridge'},
        3:{'asset':'AAPL','forecast_horizons':[1,5]},5:{'max_sector_weight':1.},
        }.get(feature,{}))
    start=time.monotonic()
    try:
        result=run_feature(feature,p)
        json.dumps(result,allow_nan=False)
        entry={'feature':feature,'status':result['status'],'seconds':round(time.monotonic()-start,2),'summary':result['summary_cards']}
    except Exception as exc:
        entry={'feature':feature,'status':'failed','error':f'{type(exc).__name__}: {exc}','seconds':round(time.monotonic()-start,2)}
    results.append(entry); print(json.dumps(entry,default=str),flush=True)
open('/tmp/ml_real_smoke_results.json','w').write(json.dumps(results,indent=2,default=str))
print(json.dumps(data_inventory(),default=str),flush=True)
