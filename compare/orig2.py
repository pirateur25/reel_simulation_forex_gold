import sys,os,time,pickle,warnings,json;warnings.filterwarnings('ignore')
sys.path.insert(0,'/tmp/oe/backtest');sys.path.insert(1,'/home/claude/fvg_bot/backtest')
os.chdir('/home/claude/zipx/forex_backtest-main')
import pandas as pd,numpy as np
import run_backtest as rb, strategy as ostrat, engine as oeng, data as odata
import realism as R
BASE="side=short;confirms=mss;conf_tfs=5m;session_start=0;session_end=24;mss_fractal=2;min_sl_pct=0.2657;tp_fib=1.5233;be_rr=2;trend_filter=0;trend_mode=both;zz_atr_trend=5.5628;ote_react=0"
def run(sym,prm=BASE,mult=None,real=True,weekend=True,news=True,start='2021-01-04',end=None,wb=0):
    rb.apply_params(prm)
    df=odata.load_csv(f'data/{sym}.csv.gz');df=df[df['time']>=pd.Timestamp(start,tz='UTC')].reset_index(drop=True)
    if end: df=df[df['time']<pd.Timestamp(end,tz='UTC')].reset_index(drop=True)
    ne,fx=R.flags(df['time'],news=news,weekend=weekend,wb=wb) if (real and (news or weekend)) else (None,None)
    fee=R.fee_pct(sym,mult) if real else 0.005
    lev=R.leverage(sym) if real else 50.0
    ostrat.DIAG.clear()
    tr,eq,st=oeng.run_backtest(df,ostrat,capital=10000.0,risk_pct=1.0,fee_pct=fee,slippage_pct=0.0,max_leverage=lev,be_rr=ostrat.PARAMS.get('be_rr'),noentry=ne,fexit=fx,**ostrat.ENGINE)
    return tr,eq,st
