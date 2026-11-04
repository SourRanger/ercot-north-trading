"""Refresh the public-data paper strategy. Run from the extracted project."""
import argparse
import csv
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from feeds import FRED, gas, market, weather
from walkforward import fit
from report import render

START = date(2024, 1, 1)
TEST = date(2025, 1, 1)
DAY = timedelta(days=1)
FEE = 1.0  # Assumed all-in round-trip cost per MWh, applied to each delivery.
FACTORS = ["spark", "north_premium", "premium_vol", "weekend", "cooling", "heating", "wind", "humidity"]


def features(day, da, rt, hubgas, wx):
    # Operate before the auction on D-1. The weekly ERCOT archive is delayed.
    days = [day - i*DAY for i in range(10, 24)]
    if any(d not in da or d not in rt for d in days):
        return None
    gday = next((day-i*DAY for i in range(14, 22) if day-i*DAY in hubgas), None)
    wday = day-3*DAY
    if gday is None or wday not in wx:
        return None
    high, low, wind, rh = wx[wday]
    temp = (high+low)/2
    premium = [rt[d]-da[d] for d in days]
    values = [mean(da[d] for d in days[:7])-7*hubgas[gday], mean(premium[:7]),
              stdev(premium), int(day.weekday()>=5), max(temp-65,0), max(65-temp,0), wind, rh]
    return values, gday, wday, days[0]


def forecast(train, x, n):
    # Clip only training outcomes to their historical 5th/95th percentiles.
    targets = sorted(y for _, y in train)
    lo, hi = targets[len(targets)//20], targets[-1-len(targets)//20]
    centers, scales, level, slopes = fit([v[:n] for v,_ in train], [min(hi,max(lo,y)) for _,y in train])
    contributions = [s*(v-c)/z for s,v,c,z in zip(slopes,x,centers,scales)]
    return level + sum(contributions), dict(zip(FACTORS, contributions)), level


def position(edge, risk):
    if abs(edge) <= FEE or risk < .01:
        return 0.
    return (1 if edge>0 else -1)*min(100,350/risk)


def research(da, rt, hubgas, wx, target):
    history, ledger, latest = [], [], None
    equity = peak = 0.
    for offset in range((target-START).days+1):
        day = START + offset*DAY
        vector = features(day,da,rt,hubgas,wx)
        if vector is None:
            continue
        x, gd, wd, md = vector
        if day >= TEST:
            train = [(v,y) for d,v,y in history if d<=day-10*DAY][-180:]
            if len(train)>=180:
                edge, terms, level = forecast(train,x,len(FACTORS))
                base = forecast(train,x,4)[0]
                risk = stdev(y for _,y in train[-30:])
                qty, baseline = position(edge,risk), position(base,risk)
                if day==target:
                    latest = dict(delivery=str(day),gas_date=str(gd),weather_date=str(wd),market_date=str(md),
                                  forecast=edge, target_mwh=qty, intercept=level, contributions=terms,
                                  features=dict(zip(FACTORS,x)))
                if day in da and day in rt:
                    move = rt[day]-da[day]
                    pnl = qty*move-abs(qty)*FEE
                    equity += pnl
                    peak = max(peak,equity)
                    ledger.append(dict(day=str(day),da=da[day],rt=rt[day],forecast=edge,mwh=qty,
                                       gross=qty*move,cost=abs(qty)*FEE,net=pnl,equity=equity,drawdown=equity-peak,
                                       no_weather=baseline*move-abs(baseline)*FEE,always_long=min(100,350/risk)*(move-FEE) if risk>=.01 else 0,
                                       always_short=min(100,350/risk)*(-move-FEE) if risk>=.01 else 0,
                                       **dict(zip(FACTORS,x))))
        if day in da and day in rt:
            history.append((day,x,rt[day]-da[day]))
    if not ledger:
        raise ValueError("Insufficient aligned observations for held-out evaluation")
    return ledger,latest


def refresh(out, cache):
    now = datetime.now(ZoneInfo("America/Chicago"))
    today = now.date()
    target = today + (1 if now.hour<10 else 2)*DAY
    cache.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(4) as pool:
        da_job, rt_job = [pool.submit(market,k,START,today,cache) for k in ("DA","RT")]
        gas_job = pool.submit(gas)
        wx_job = pool.submit(weather,START,today)
        da, das = da_job.result()
        rt, rts = rt_job.result()
        hubgas = gas_job.result()
        wx, weather_url = wx_job.result()
    ledger, signal = research(da,rt,hubgas,wx,target)
    summary = dict(refreshed=now.isoformat(timespec="seconds"),target=str(target),signal=signal,
                   first=ledger[0]["day"],last=ledger[-1]["day"],days=len(ledger),
                   active=sum(r["mwh"]!=0 for r in ledger),net=sum(r["net"] for r in ledger),
                   drawdown=min(r["drawdown"] for r in ledger),no_weather=sum(r["no_weather"] for r in ledger),
                   always_long=sum(r["always_long"] for r in ledger),double_cost_net=sum(r["net"]-r["cost"] for r in ledger),
                   always_short=sum(r["always_short"] for r in ledger),
                   latest_dates={k:str(max(v)) for k,v in [("day_ahead",da),("real_time",rt),("gas",hubgas),("weather",wx)]},
                   sources=das+rts+[("gas",FRED,""),("weather",weather_url,"")])
    out.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(dir=out) as folder:
        stage=Path(folder)
        with (stage/"daily.csv").open("w",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=ledger[0])
            writer.writeheader()
            writer.writerows(ledger)
        (stage/"status.json").write_text(json.dumps(summary,indent=2))
        (stage/"dashboard.html").write_text(render(summary,ledger),encoding="utf-8")
        db=sqlite3.connect(stage/"research.sqlite")
        try:
            keys=list(ledger[0])
            db.execute("CREATE TABLE daily(day TEXT PRIMARY KEY,"+",".join(k+" REAL" for k in keys[1:])+")")
            db.executemany("INSERT INTO daily VALUES("+",".join("?"*len(keys))+")",[tuple(r.values()) for r in ledger])
            db.execute("CREATE TABLE inputs(day TEXT PRIMARY KEY, da REAL, rt REAL, gas REAL, high_f REAL, low_f REAL, wind_kt REAL, humidity_pct REAL)")
            dates=sorted(set(da)|set(rt)|set(wx)|{d for d in hubgas if START<=d<=today})
            db.executemany("INSERT INTO inputs VALUES(?,?,?,?,?,?,?,?)",[(str(d),da.get(d),rt.get(d),hubgas.get(d),*wx.get(d,[None]*4)) for d in dates])
            db.commit()
        finally:
            db.close()
        for name in ("research.sqlite","daily.csv","status.json","dashboard.html"):
            os.replace(stage/name,out/name)
    if signal:
        journal = sqlite3.connect(out/"paper_journal.sqlite")
        try:
            journal.execute("CREATE TABLE IF NOT EXISTS decisions(delivery TEXT PRIMARY KEY, recorded TEXT, forecast REAL, mwh REAL, realized_net REAL)")
            journal.execute("INSERT OR IGNORE INTO decisions VALUES(?,?,?,?,NULL)",
                            (str(target),summary["refreshed"],signal["forecast"],signal["target_mwh"]))
            for raw,qty in journal.execute("SELECT delivery,mwh FROM decisions WHERE realized_net IS NULL").fetchall():
                delivery = date.fromisoformat(raw)
                if delivery in da and delivery in rt:
                    journal.execute("UPDATE decisions SET realized_net=? WHERE delivery=?",
                                    (qty*(rt[delivery]-da[delivery])-abs(qty)*FEE,raw))
            journal.commit()
        finally:
            journal.close()
    print(f"{summary['days']} held-out days through {summary['last']}, net USD {summary['net']:,.2f}",flush=True)
    print(json.dumps(signal or {"status":"No paper signal: required dated inputs unavailable"}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache",type=Path,default=Path(".market-cache"))
    parser.add_argument("--out",type=Path,default=Path("public_results"))
    parser.add_argument("--watch",action="store_true",help="Refresh hourly while this process is running")
    args=parser.parse_args()
    while True:
        try:
            refresh(args.out,args.cache)
        except Exception as err:
            if not args.watch:
                raise
            print(f"Refresh failed at {datetime.now(timezone.utc).isoformat()}: {err}. Previous files retain their original timestamp.",flush=True)
        if not args.watch:
            break
        time.sleep(3600)
