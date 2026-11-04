"""Public market and weather feeds. Only document-versioned archives are cached."""
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile
from openpyxl import load_workbook

ERCOT = "https://www.ercot.com/misapp/servlets/"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DHHNGSP"
IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
VARS = ["max_temp_f", "min_temp_f", "avg_wind_speed_kts", "avg_rh"]


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "EnergyResearch/1.0"}), timeout=90) as reply:
        return reply.read()


def market(kind, start, end, cache):
    report = 13060 if kind == "DA" else 13061
    docs = json.loads(fetch(ERCOT + f"IceDocListJsonWS?reportTypeId={report}"))["ListDocsByRptTypeRes"]["DocumentList"]
    prices, sources = {}, []
    for year in range(start.year, end.year + 1):
        candidates = [x["Document"] for x in docs if x["Document"]["FriendlyName"].endswith("_" + str(year))]
        if not candidates:
            continue
        doc = max(candidates, key=lambda x: x["PublishDate"])
        url = "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=" + doc["DocID"]
        local = cache / (kind + "-" + doc["DocID"] + ".json")
        if local.exists():
            annual = json.loads(local.read_text())
        else:
            print("Reading", kind, year, flush=True)
            groups = defaultdict(list)
            with ZipFile(BytesIO(fetch(url))) as archive:
                for name in archive.namelist():
                    if not name.lower().endswith(".xlsx"):
                        continue
                    book = load_workbook(BytesIO(archive.read(name)), read_only=True, data_only=True)
                    for sheet in book:
                        rows = iter(sheet.values)
                        header = [str(v).strip().upper().replace(" ", "") for v in next(rows, ())]
                        keys = [v for v in header if v in ("SETTLEMENTPOINT", "SETTLEMENTPOINTNAME")]
                        if not keys or "SETTLEMENTPOINTPRICE" not in header:
                            continue
                        hub = header.index(keys[0])
                        ix = header.index("SETTLEMENTPOINTPRICE")
                        for row in rows:
                            if not row or row[hub] != "HB_NORTH" or row[ix] is None:
                                continue
                            raw = row[0]
                            day = raw.date() if isinstance(raw, datetime) else datetime.strptime(str(raw), "%m/%d/%Y").date()
                            groups[day.isoformat()].append(float(row[ix]))
                    book.close()
            annual = {}
            for day, marks in groups.items():
                # Local operating days have 23/25 hours at US DST transitions.
                d = date.fromisoformat(day)
                hours = 23 if d.month == 3 and d.weekday() == 6 and 8 <= d.day <= 14 else 25 if d.month == 11 and d.weekday() == 6 and d.day <= 7 else 24
                if len(marks) == hours * (1 if kind == "DA" else 4) and all(map(math.isfinite, marks)):
                    annual[day] = mean(marks)
            if not annual:
                raise ValueError(f"No complete {kind} days in {doc['FriendlyName']}")
            tmp = local.with_suffix(".tmp")
            tmp.write_text(json.dumps(annual))
            tmp.replace(local)
        sources.append((kind, url, doc["PublishDate"]))
        prices.update({date.fromisoformat(k): v for k, v in annual.items() if start.isoformat() <= k <= end.isoformat()})
    return prices, sources


def weather(start, end):
    params = dict(network="TX_ASOS", stations="DFW", var=VARS, format="csv", na="blank",
                  year1=start.year, month1=start.month, day1=start.day, year2=end.year, month2=end.month, day2=end.day)
    url = IEM + "?" + urlencode(params, doseq=True)
    result = {}
    for row in csv.DictReader(StringIO(fetch(url).decode())):
        try:
            values = [float(row[v]) for v in VARS]
        except (ValueError, TypeError):
            continue
        if all(map(math.isfinite, values)):
            result[date.fromisoformat(row["day"])] = values
    return result, url


def gas():
    rows = csv.DictReader(StringIO(fetch(FRED).decode("utf-8-sig")))
    return {date.fromisoformat(r["observation_date"]): float(r["DHHNGSP"]) for r in rows
            if r["DHHNGSP"] not in ("", ".")}

