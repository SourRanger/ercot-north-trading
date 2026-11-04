"""Rolling ridge forecast of the spread move after the execution lag."""
from math import ceil
from statistics import mean, stdev

TRAIN, BLOCK, VOL_WINDOW = 90, 20, 20
FACTORS = ("spread", "load", "thermal_stress")


def fit(samples, targets):
    centers = list(map(mean, zip(*samples)))
    scales = [stdev(col) or 1 for col in zip(*samples)]
    x = [[(v - c) / s for v, c, s in zip(row, centers, scales)] for row in samples]
    intercept = mean(targets)
    # Normal equations for standardized factors, with ridge penalty 9.
    count = len(centers)
    matrix = [[sum(r[i] * r[j] for r in x) + (9 if i == j else 0)
               for j in range(count)] + [sum(r[i] * (y - intercept) for r, y in zip(x, targets))]
              for i in range(count)]
    for i in range(count):
        pivot = matrix[i][i]
        matrix[i] = [v / pivot for v in matrix[i]]
        for j in range(count):
            if j != i:
                multiple = matrix[j][i]
                matrix[j] = [a - multiple * b for a, b in zip(matrix[j], matrix[i])]
    return centers, scales, intercept, [r[-1] for r in matrix]


def evaluate(db, cap, fee, budget):
    rows = db.execute("SELECT day, spread, load, thermal_stress FROM economics ORDER BY day").fetchall()
    x = [r[1:] for r in rows]
    spreads = [r[1] for r in rows]
    db.execute("""CREATE TABLE forecasts(day TEXT PRIMARY KEY, train_first TEXT, train_last_label TEXT,
               forecast REAL, volatility REAL, target_mwh REAL, spread_beta REAL, load_beta REAL, weather_beta REAL)""")
    for t in range(TRAIN + 1, len(rows)):
        if (t - TRAIN - 1) % BLOCK == 0:
            start = t - TRAIN - 1
            centers, scales, intercept, slopes = fit(x[start:t-1],
                [spreads[i+2] - spreads[i+1] for i in range(start, t-1)])
            training_dates = rows[start][0], rows[t][0]
        forecast = intercept + sum(b * (v - c) / s for b, v, c, s in zip(slopes, x[t], centers, scales))
        vol = stdev(spreads[i] - spreads[i-1] for i in range(t-VOL_WINDOW+1, t+1))
        size = min(cap, budget / vol) if vol > 1e-10 else 0
        target = size if forecast > 2 * fee else -size if forecast < -2 * fee else 0
        db.execute("INSERT INTO forecasts VALUES(?,?,?,?,?,?,?,?,?)",
                   (rows[t][0], *training_dates, forecast, vol, target, *slopes))
    db.executescript("""
    CREATE TABLE walkforward AS
    WITH positions AS (
      SELECT l.*, lag(f.target_mwh,2) OVER w AS held_mwh,
             lag(f.day,2) OVER w AS decision_day
      FROM ledger l LEFT JOIN forecasts f USING(day) WINDOW w AS (ORDER BY l.day)
    ), eligible AS (
      SELECT *, abs(held_mwh-lag(held_mwh,1,0) OVER w)+last_day*abs(held_mwh) AS traded_mwh,
             row_number() OVER w AS seq
      FROM positions WHERE decision_day IS NOT NULL WINDOW w AS (ORDER BY day)
    ), pnl AS (
      SELECT day, decision_day, held_mwh, traded_mwh, traded_mwh*fee AS fees,
             held_mwh*spread_change-traded_mwh*fee AS net_pnl,
             size_mwh*(spread_change-fee*((seq=1)+last_day)) AS benchmark_pnl
      FROM eligible CROSS JOIN settings
    ), curve AS (
      SELECT *,sum(net_pnl) OVER (ORDER BY day) AS equity FROM pnl
    )
    SELECT *,equity-max(0,max(equity) OVER (ORDER BY day)) AS drawdown FROM curve ORDER BY day;
    """)
    losses = [r[0] for r in db.execute("SELECT net_pnl FROM walkforward ORDER BY net_pnl")]
    k = ceil(.05 * len(losses))
    db.execute("CREATE TABLE risk(test_days INTEGER, tail_days INTEGER, worst_tail_mean_pnl REAL, risk_budget_usd REAL)")
    db.execute("INSERT INTO risk VALUES(?,?,?,?)", (len(losses), k, mean(losses[:k]) if k else None, budget))

