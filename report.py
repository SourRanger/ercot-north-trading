"""Local, self-refreshing HTML report. No server or external scripts required."""
from collections import defaultdict
from html import escape


def render(summary, rows):
    def usd(n):
        return f"-${abs(n):,.0f}" if n < 0 else f"${n:,.0f}"

    signal = summary["signal"]
    if signal:
        qty=signal["target_mwh"]
        side="Buy DA / sell RT" if qty>0 else "Sell DA / buy RT" if qty<0 else "Flat"
        title=f"{side} · {abs(qty):.1f} MWh"
        detail=f"Predicted RT less DA: {signal['forecast']:+.2f} USD/MWh. Assumed round-trip cost: 1.00 USD/MWh."
        vintages=f"Market window ends {signal['market_date']} · weather {signal['weather_date']} · Henry Hub {signal['gas_date']}"
        factors="".join(f"<tr><td>{k.replace('_',' ').title()}</td><td>{v:+.2f}</td></tr>"
                        for k,v in sorted(signal["contributions"].items(),key=lambda item:-abs(item[1])))
        factors+=f"<tr><td>Intercept</td><td>{signal['intercept']:+.2f}</td></tr>"
    else:
        title,detail,vintages,factors="Signal unavailable","One or more required dated observations are missing.","",""
    monthly=defaultdict(lambda:[0.,0.,0.,0.])
    for r in rows:
        totals=monthly[r["day"][:7]]
        for i,key in enumerate(("net","no_weather","always_long","always_short")):
            totals[i]+=r[key]
    table="".join("<tr><td>"+month+"</td>"+"".join("<td>"+usd(v)+"</td>" for v in totals)+"</tr>"
                  for month,totals in reversed(monthly.items()))
    values=[0]+[r["equity"] for r in rows]
    best_short=max(rows,key=lambda r:r["always_short"])
    short_check=f"Always-short net: {usd(summary['always_short'])}. Best day: {usd(best_short['always_short'])} on {best_short['day']}. Excluding that day: {usd(summary['always_short']-best_short['always_short'])}."
    low,high=min(values),max(values)
    points=" ".join(f"{i*900/(len(values)-1):.1f},{140-(v-low)*130/(high-low or 1):.1f}" for i,v in enumerate(values))
    cards="".join(f"<div><small>{name}</small><strong>{usd(summary[key])}</strong></div>"
                  for name,key in (("Net P&L","net"),("Max drawdown","drawdown"),("Without weather","no_weather"),("Double cost","double_cost_net")))
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="120">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>North Hub research</title>
<style>body{{max-width:980px;margin:40px auto;padding:0 20px;background:#f4f6f2;color:#173e40;font:16px/1.5 system-ui}}h1,h2,p{{margin:.35em 0}}section{{background:white;padding:22px;margin:14px 0;border-top:3px solid #307c76}}small{{color:#456558}}.cards{{display:flex;flex-wrap:wrap;gap:32px}}strong{{display:block;font-size:24px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:5px 10px;text-align:right;border-bottom:1px solid #ddd}}td:first-child,th:first-child{{text-align:left}}svg{{width:100%;height:150px}}</style>
<h1>ERCOT North Hub</h1><p>Public-data paper book · refreshed {escape(summary['refreshed'])}</p>
<section><small>DELIVERY {summary['target']}</small><h2>{title}</h2><p>{detail}</p><small>{vintages}</small></section>
<section><h2>Walk-forward results</h2><p>{summary['first']} through {summary['last']} · {len(rows)} scored delivery days</p>
<div class="cards">{cards}</div><p>Cumulative net P&L, USD</p><svg viewBox="0 0 900 150" preserveAspectRatio="none"><polyline points="{points}" fill="none" stroke="#147a70" stroke-width="2"/></svg></section>
<section><h2>Forecast contributions</h2><table><tr><th>Factor</th><th>USD/MWh</th></tr>{factors}</table></section>
<section><h2>Monthly net P&L</h2><p>Always short sells day-ahead and buys real-time at the same risk size as always long.</p><p>{short_check}</p><table><tr><th>Delivery</th><th>Full</th><th>Without weather</th><th>Always long</th><th>Always short</th></tr>{table}</table></section>
<small>Assumes both legs clear at published prices. Model fills and costs are hypothetical. The timestamp records the last successful refresh.</small></html>"""
