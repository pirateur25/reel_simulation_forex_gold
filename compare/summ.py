import pickle,sys,numpy as np,pandas as pd
def seg(e,a,b):
    x=e[(e.index>=a)&(e.index<b)]
    if len(x)<10: return (np.nan,np.nan)
    c=(1+x)/(1+x.iloc[0]);return ((c.iloc[-1]-1)*100,((c/c.cummax()-1).min())*100)
def show(path,title):
    out=pickle.load(open(path,'rb'));print(title)
    print(f"{'actif':7s} | 2021-24 ret/DD | 2025-26 ret/DD | total ret/DD  n  E(R)")
    T=lambda x:pd.Timestamp(x,tz='UTC')
    for s,(tr,e) in out.items():
        a=seg(e,T('2021-01-01'),T('2025-01-01'));b=seg(e,T('2025-01-01'),T('2027-01-01'));c=seg(e,T('2021-01-01'),T('2027-01-01'))
        r=tr['r'] if 'r' in tr else (tr['pnl']/tr['risk_amount']).where(tr['risk_amount']>0,0) if 'risk_amount' in tr else tr['pnl']*0
        print(f"{s:7s} | {a[0]:+6.1f}/{a[1]:6.1f} | {b[0]:+6.1f}/{b[1]:6.1f} | {c[0]:+6.1f}/{c[1]:6.1f} {len(tr):4d} {r.mean():+.2f}")
if __name__=='__main__': show(sys.argv[1],sys.argv[2])
