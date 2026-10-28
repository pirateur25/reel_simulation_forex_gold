import numpy as np,pandas as pd,pickle,warnings;warnings.filterwarnings('ignore')
def load(f,assets):
    o=pickle.load(open(f,'rb'));return {a:o[a][1] for a in assets}
def build(parts):
    """parts: liste de (dict actif->série, échelle). Retourne index, équité combinée (fraction du capital)."""
    cols={}
    for k,(d,sc) in enumerate(parts):
        for a,s in d.items(): cols[(k,a)]=s*sc
    df=pd.concat(cols,axis=1).sort_index().ffill().fillna(0.0)
    return df.index,df.sum(axis=1).to_numpy()
def prep(idx):
    ns=idx.tz_convert('UTC').as_unit('ns');day=((ns-pd.Timedelta(hours=22)).normalize()).asi8;first=np.r_[True,day[1:]!=day[:-1]]
    return ns.asi8,np.maximum.accumulate(np.where(first,np.arange(len(day)),0))
def phase(E,dd,s,T,ML,DL,W):
    seg=E[s:s+W]-E[s];hit=seg>=T;lose=(seg<=-ML)|(dd[s:s+W]<=-DL)
    ih=np.argmax(hit) if hit.any() else 10**9;il=np.argmax(lose) if lose.any() else 10**9
    if ih==10**9 and il==10**9:return 'open',None
    return ('pass',s+ih) if ih<il else ('fail',s+il)
def chal(idx,E,rule,sf='2021-01-04',st='2026-04-30',step=288*3,W=288*370):
    T1,T2,DL,ML=rule;ts,dop=prep(idx);dd=E-E[dop]
    S=np.arange(np.searchsorted(ts,pd.Timestamp(sf,tz='UTC').value),np.searchsorted(ts,pd.Timestamp(st,tz='UTC').value),step);res=[]
    for s in S:
        r1,t1=phase(E,dd,s,T1,ML,DL,W)
        if r1!='pass':res.append((r1,None));continue
        r2,t2=phase(E,dd,t1+1,T2,ML,DL,W);res.append((r2,(ts[t2]-ts[s])/86400e9 if r2=='pass' else None))
    n=len(res);ok=[r[1] for r in res if r[0]=='pass']
    return len(ok)/n*100,sum(r[0]=='fail' for r in res)/n*100,(np.median(ok) if ok else np.nan)
def stats(idx,E):
    s=pd.Series(E,index=idx);d=s.resample('1D').last().diff().dropna();c=1+s;yrs=(idx[-1]-idx[0]).days/365.25
    return s.iloc[-1]*100,((c/c.cummax()-1).min())*100,d.mean()/d.std()*np.sqrt(252),s.iloc[-1]*100/yrs
FV=['EURUSD','GBPUSD','USDJPY','XAUUSD'];OR=['EURUSD','USDJPY','XAUUSD']
RULES={'FTMO':(0.10,0.05,0.05,0.10),'FP Standard':(0.08,0.05,0.05,0.10)}
if __name__=='__main__':
    f1,o1='/tmp/univ_fvg_2.0.pkl','/tmp/univ_orig_2.0.pkl';f2,o2='/tmp/univ_fvg_2.0_we.pkl','/tmp/univ_orig_2.0_we.pkl'
    F=load(f1,FV);O=load(o1,OR);F2=load(f2,FV);O2=load(o2,OR)
    combos=[('Original seule 0,75',[(O,.75)]),('Original seule 1,0',[(O,1.0)]),('FVG seule 0,5',[(F,.5)]),('FVG seule 0,75',[(F,.75)]),
            ('FVG 0,5 + Orig 0,5',[(F,.5),(O,.5)]),('FVG 0,5 + Orig 0,75',[(F,.5),(O,.75)]),('FVG 0,75 + Orig 0,5',[(F,.75),(O,.5)]),('FVG 0,75 + Orig 0,75',[(F,.75),(O,.75)]),('FVG 0,5 + Orig 1,0',[(F,.5),(O,1.0)])]
    print('SCÉNARIO SWING (détention WE autorisée, coûts×2) — challenge FTMO / FP Standard : réussi% / échec% / durée médiane j ; [départs 2025+]')
    for k,parts in combos:
        idx,E=build(parts);r,dd,sh,ann=stats(idx,E);line=f"{k:22s} {r:+6.0f}% ({ann:+4.1f}%/an) DD {dd:5.1f}% Sh {sh:4.2f} |"
        for pn,rl in RULES.items():
            a=chal(idx,E,rl);b=chal(idx,E,rl,sf='2025-01-01',step=288);line+=f" {pn} {a[0]:3.0f}/{a[1]:2.0f}/{a[2]:3.0f}j [{b[0]:3.0f}/{b[1]:2.0f}] |"
        print(line,flush=True)
    print('\nSCÉNARIO COMPTE FINANCÉ STANDARD (fermeture WE + annonces) :')
    for k,parts in [('Orig 0,75',[(O2,.75)]),('FVG 0,75',[(F2,.75)]),('FVG 0,5 + Orig 0,75',[(F2,.5),(O2,.75)]),('FVG 0,75 + Orig 0,75',[(F2,.75),(O2,.75)])]:
        idx,E=build(parts);r,dd,sh,ann=stats(idx,E);print(f"{k:22s} {r:+6.0f}% ({ann:+4.1f}%/an) DD {dd:5.1f}% Sh {sh:4.2f}")
