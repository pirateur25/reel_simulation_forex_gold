import sys,json,warnings,pickle,time;warnings.filterwarnings('ignore');sys.path.insert(0,'/home/claude/fvg_bot/backtest')
import data,strategy,engine,realism as R,numpy as np,pandas as pd
mode=sys.argv[1]   # 'fvg' ou 'orig'
ALL=['EURUSD','GBPUSD','USDCHF','USDJPY','XAUUSD','AUDUSD','NZDUSD','USDCAD','EURGBP','EURJPY','GBPJPY','XAGUSD','US30','GER40','NAS100']
mult=float(sys.argv[2]) if len(sys.argv)>2 else 2.0
weekend=(len(sys.argv)>3 and sys.argv[3]=='we')
out={}
if mode=='fvg':
    best={**strategy.PARAMS,**json.load(open('/home/claude/fvg_bot/results/best_params.json'))}
    for s in ALL:
        P=data.PairData(s,'/home/claude/fvg_bot/data');sg=strategy.signals(P,best)
        ne,fx=R.flags(P.times,news=weekend,weekend=weekend) if weekend else (None,None)
        tr,eq,st=engine.run(P,sg,10000.0,1.0,R.fee_pct(s,mult),R.leverage(s),best['be_rr'],best['ttl'],noentry=ne,fexit=fx)
        t=pd.DatetimeIndex(P.times).tz_convert('UTC');out[s]=(tr,pd.Series(eq/1e4-1,index=t))
else:
    sys.path.insert(0,'/tmp');import importlib;sys.argv=[sys.argv[0]];o=importlib.import_module('orig2')
    for s in ALL:
        tr,eq,st=o.run(s,mult=mult,real=True,weekend=weekend,news=weekend)
        e=pd.Series(np.asarray(eq,float)/1e4-1,index=pd.DatetimeIndex(eq.index).tz_convert('UTC') if eq.index.tz else pd.DatetimeIndex(eq.index).tz_localize('UTC'));out[s]=(tr,e)
pickle.dump(out,open(f'/tmp/univ_{mode}_{mult}{"_we" if weekend else ""}.pkl','wb'))
def seg(e,a,b):
    x=e[(e.index>=a)&(e.index<b)]
    if len(x)<10: return (np.nan,np.nan)
    c=(1+x)/(1+x.iloc[0]);return ((c.iloc[-1]-1)*100,((c/c.cummax()-1).min())*100)
print(f"{mode} coûts×{mult} {'week-end+annonces' if weekend else 'détention week-end autorisée'}")
print(f"{'actif':7s} | 2021-24 ret/DD | 2025-26 ret/DD | total ret/DD  n  E(R)")
for s,(tr,e) in out.items():
    a=seg(e,pd.Timestamp('2021-01-01',tz='UTC'),pd.Timestamp('2025-01-01',tz='UTC'));b=seg(e,pd.Timestamp('2025-01-01',tz='UTC'),pd.Timestamp('2027-01-01',tz='UTC'));c=seg(e,pd.Timestamp('2021-01-01',tz='UTC'),pd.Timestamp('2027-01-01',tz='UTC'))
    r=tr['r'] if 'r' in tr else (tr['pnl']/tr['risk_amount'] if 'risk_amount' in tr else tr['pnl']*0)
    print(f"{s:7s} | {a[0]:+6.1f}/{a[1]:6.1f} | {b[0]:+6.1f}/{b[1]:6.1f} | {c[0]:+6.1f}/{c[1]:6.1f} {len(tr):4d} {r.mean():+.2f}")
