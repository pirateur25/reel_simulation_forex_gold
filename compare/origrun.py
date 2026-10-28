import sys,pickle,warnings;warnings.filterwarnings('ignore')
mult=float(sys.argv[1]);we=(len(sys.argv)>2 and sys.argv[2]=='we');wb=int(sys.argv[3]) if len(sys.argv)>3 else 0
sys.path.insert(0,'/tmp');import orig2 as o
import numpy as np,pandas as pd
ALL=['EURUSD','GBPUSD','USDCHF','USDJPY','XAUUSD','AUDUSD','NZDUSD','USDCAD','EURGBP','EURJPY','GBPJPY','XAGUSD','US30','GER40','NAS100']
out={}
for s in ALL:
    tr,eq,st=o.run(s,mult=mult,real=True,weekend=we,news=we,wb=wb)
    ix=pd.DatetimeIndex(eq.index);ix=ix.tz_convert('UTC') if ix.tz else ix.tz_localize('UTC')
    out[s]=(tr,pd.Series(np.asarray(eq,float)/1e4-1,index=ix))
pickle.dump(out,open(f'/tmp/univ_orig_{mult}{"_we" if we else ""}.pkl','wb'))
