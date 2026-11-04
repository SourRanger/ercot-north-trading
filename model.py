"""Run the daily Henry Hub / ERCOT spread research model. Python 3.10+."""
import argparse
import csv
from datetime import date, timedelta
import math
from pathlib import Path
import random
import sqlite3
import tempfile
from walkforward import evaluate

FIELDS = ["day", "gas", "power", "temp", "load"]


def demo():
    rng = random.Random(913)
    gas, weather, premium = 3, 0, 0
    for i in range(365):
        weather = .75 * weather + rng.gauss(0, 3)
        temp = 70 - 18 * math.cos(2 * math.pi * (i - 18) / 365) + weather
        load = 39000 + 800 * abs(temp - 65) + rng.gauss(0, 2200)
        gas = max(.5, gas + .06 * (3 - gas) + rng.gauss(0, .09))
        premium = .5 * premium + rng.gauss(0, 5)
        power = 7 * gas + 4 + (load - 40000) / 1700 + premium
        yield [(date(2025, 1, 1) + timedelta(days=i)).isoformat(),
               round(gas, 3), round(power, 2), round(temp, 2), round(load, 1)]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"Expected headers {FIELDS}")
        previous = None
        for n, row in enumerate(reader, 2):
            try:
                day = date.fromisoformat(row["day"])
                values = [float(row[k]) for k in FIELDS[1:]]
                if None in row or not all(map(math.isfinite, values)) or values[0] <= 0 or values[3] <= 0:
                    raise ValueError("finite inputs and positive gas and load required")
                if previous and day <= previous:
                    raise ValueError("dates must be unique and increasing")
            except (TypeError, ValueError) as e:
                raise ValueError(f"CSV row {n}: {e}") from e
            previous = day
            yield [day.isoformat(), *values]


def run(rows, db, settings):
    schema = Path(__file__).with_name("model.sql").read_text()
    tables, views = schema.split("CREATE VIEW", 1)
    db.executescript(tables)
    db.execute("INSERT INTO settings VALUES(?,?,?,?,?)", settings)
    db.executemany("INSERT INTO market VALUES(?,?,?,?,?)", rows)
    if db.execute("SELECT count(*) FROM market").fetchone()[0] < 23:
        raise ValueError("At least 23 observations required for warm-up and execution")
    db.executescript("CREATE VIEW" + views)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="Aligned daily observations. Default uses synthetic data.")
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--risk-budget", type=float, default=350, help="Daily spread volatility budget in USD")
    for name, value in [("heat-rate", 7), ("variable-om", 3), ("size-mwh", 100), ("fee", .15)]:
        parser.add_argument("--" + name, type=float, default=value)
    a = parser.parse_args()
    if not math.isfinite(a.risk_budget) or a.risk_budget <= 0:
        parser.error("Risk budget must be finite and positive")
    params = (a.heat_rate, a.variable_om, a.size_mwh, a.fee)
    if not all(map(math.isfinite, params)) or min(a.heat_rate, a.size_mwh) <= 0 or min(a.fee, a.variable_om) < 0:
        parser.error("Heat rate and MWh must be positive. O&M and fee must be nonnegative.")
    a.out.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory(dir=a.out) as stage:
        stage = Path(stage)
        db = sqlite3.connect(stage / "market.sqlite")
        try:
            run(read_csv(a.csv) if a.csv else demo(), db, (*params, str(a.csv or "Synthetic sample, seed 913")))
            evaluate(db, a.size_mwh, a.fee, a.risk_budget)
            db.commit()
            for filename, query in [("market", "SELECT * FROM market ORDER BY day"),
                                    ("ledger", "SELECT * FROM ledger ORDER BY day"),
                                    ("forecasts", "SELECT * FROM forecasts ORDER BY day"),
                                    ("walkforward", "SELECT * FROM walkforward ORDER BY day"),
                                    ("risk", "SELECT * FROM risk")]:
                cursor = db.execute(query)
                with (stage / (filename + ".csv")).open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([c[0] for c in cursor.description])
                    writer.writerows(cursor)
            pnl, dd = db.execute("SELECT sum(net_pnl), min(drawdown) FROM ledger").fetchone()
        finally:
            db.close()
        for file in stage.iterdir():
            file.replace(a.out / file.name)
    print(f"Net P&L {pnl:,.2f} USD | Maximum drawdown {dd:,.2f} USD | {a.out.resolve()}")


if __name__ == "__main__":
    main()
