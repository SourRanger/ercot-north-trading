from pathlib import Path
import csv
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit

rows=list(csv.DictReader(open("public_results/daily.csv")))
out=Path("artifacts/ERCOT North Trading Memo.pdf")
c=Canvas(str(out),pagesize=(612,792))
c.setTitle("ERCOT North | Gas and power trading research")
c.setAuthor("")
for face,file in [("Body","segoeui"),("Bold","segoeuib")]:
    pdfmetrics.registerFont(TTFont(face,f"C:/Windows/Fonts/{file}.ttf"))
ink="#172D3C"; teal="#087C74"; grey="#4D606B"; amber="#996215"
def line(x,y,t,size=10,face="Body",color=ink):
    c.setFillColor(HexColor(color));c.setFont(face,size);c.drawString(x,792-y,t)
def para(x,y,t,w,size=10,leading=14):
    for s in simpleSplit(t,"Body",size,w):
        line(x,y,s,size);y+=leading
    return y
def rule(y):
    c.setStrokeColor(HexColor("#CDDBDB"));c.line(40,792-y,572,792-y)
def tag(y,t):line(40,y,t,9,"Bold",teal)
def box(x,y,w,h,color):
    c.setFillColor(HexColor(color));c.rect(x,792-y-h,w,h,fill=1,stroke=0)

tag(38,"INDEPENDENT COMMODITY RESEARCH");line(452,38,"04 NOVEMBER 2026",9,"Bold",grey)
line(40,83,"Trading the ERCOT North power premium",25,"Bold")
line(40,107,"Henry Hub gas economics, day-ahead pricing and real-time settlement risk",12,"Body",grey)
box(40,127,532,68,"#E8F3F0")
line(54,148,"TRADE DECISION   /   NOVEMBER 6 DELIVERY",9,"Bold",teal)
para(54,170,"Stay flat. The model favors selling day-ahead and buying real-time by $0.93/MWh. The assumed $1.00/MWh round-trip cost consumes that edge.",499,11,15)
tag(220,"MARKET THESIS")
para(40,240,"A gas plant with a heat rate of 7 MMBtu/MWh needs another $7/MWh of power revenue when gas rises $1/MMBtu. I tested whether the resulting spark spread, recent ERCOT premiums and DFW weather could identify when day-ahead power was expensive relative to real-time power.",532)
tag(301,"HISTORICAL PAPER P&L");line(307,301,"669 delivery days   /   Jan 2025 to Oct 2026",9,"Body",grey)
line(40,322,"Cumulative net P&L, USD thousands",10,"Bold")
series=[[],[]];total=0
for r in rows:
    total+=float(r["always_short"]);series[0].append(total);series[1].append(float(r["equity"]))
x0,x1=84,563; yt,yb=343,461
lo,hi=-45000,50000
def point(i,v):return x0+(x1-x0)*i/(len(rows)-1),792-(yb-(v-lo)/(hi-lo)*(yb-yt))
for v in [-40000,0,40000]:
    _,y=point(0,v);c.setStrokeColor(HexColor("#CBD7D7"));c.setLineWidth(.5);c.line(x0,y,x1,y);line(45,792-y+3,f"{v//1000:+d}" if v else "0",9,"Body",grey)
for vs,color in zip(series,[teal,amber]):
    p=c.beginPath();p.moveTo(*point(0,vs[0]))
    for i,v in enumerate(vs[1:],1):p.lineTo(*point(i,v))
    c.setLineWidth(1.6);c.setStrokeColor(HexColor(color));c.drawPath(p)
idx=next(i for i,r in enumerate(rows) if r["day"]=="2026-01-26")
x,y=point(idx,series[0][idx]);c.setFillColor(HexColor(teal));c.circle(x,y,3.2,stroke=0,fill=1)
line(84,476,"Jan 2025",8,"Body",grey);line(x-23,476,"Jan 2026",8,"Body",grey);line(527,476,"Oct 2026",8,"Body",grey)
line(84,497,"Always short day-ahead   +$37,912",10,"Bold",teal)
line(336,497,"Weather model   -$36,295",10,"Bold",amber)
rule(511)
tag(531,"WHAT DROVE THE RETURN")
para(40,551,"On January 26, day-ahead power averaged $694.03/MWh against $167.42/MWh in real time. Selling day-ahead and buying back 77.62 MWh in real time earned $40,799 after costs. Excluding that day, the short benchmark lost $2,887. The weather model held zero exposure that day.",532)
tag(615,"RISK DECISION")
para(40,635,"Keep the strategy in paper trading. Adding weather reduced net P&L by $26,250 versus the same model trained without weather. The next test would use weather forecasts available before the auction and track the premium prospectively, including fills and settlement charges.",532)
rule(689)
line(40,706,"RESEARCH IMPLEMENTATION",8,"Bold",teal)
para(40,723,"Python refreshes public feeds and fits each forecast on 180 prior observations. SQLite stores settlements and dated paper signals. Excel reconciles positions, fees and daily P&L. Fills are hypothetical.",532,9,12)
for x,txt,url in [(40,"ERCOT settlement archives","https://www.ercot.com/mktinfo/prices"),(206,"EIA Henry Hub via FRED","https://fred.stlouisfed.org/series/DHHNGSP"),(365,"Iowa Environmental Mesonet","https://mesonet.agron.iastate.edu/request/daily.phtml?network=TX_ASOS")]:
    line(x,769,txt,8,"Body",teal);c.linkURL(url,(x,20,x+145,33),relative=0)
c.save()

