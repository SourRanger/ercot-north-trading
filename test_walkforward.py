import sqlite3
import unittest

from model import demo, run
from walkforward import evaluate


def sample(rows):
    db = sqlite3.connect(":memory:")
    run(rows, db, (7, 3, 100, .15, "test"))
    evaluate(db, 100, .15, 350)
    return db


class TimingTests(unittest.TestCase):
    def test_later_observations_cannot_change_earlier_forecasts(self):
        rows = list(demo())
        short, full = sample(rows[:150]), sample(rows)
        sql = "SELECT * FROM forecasts WHERE day <= ? ORDER BY day"
        cutoff = (rows[149][0],)
        self.assertEqual(short.execute(sql, cutoff).fetchall(), full.execute(sql, cutoff).fetchall())
        short.close()
        full.close()

    def test_execution_lag_costs_and_cap(self):
        rows = list(demo())
        db = sample(rows)
        ledger = db.execute("SELECT day,decision_day,held_mwh,fees,net_pnl FROM walkforward ORDER BY day").fetchall()
        self.assertEqual(len(ledger), len(rows)-93)
        prev = 0
        for i, (day, decision, qty, fees, pnl) in enumerate(ledger, 93):
            self.assertEqual((day, decision), (rows[i][0], rows[i-2][0]))
            self.assertLessEqual(abs(qty), 100)
            self.assertAlmostEqual(fees, .15*(abs(qty-prev)+(abs(qty) if i==len(rows)-1 else 0)))
            change = rows[i][2]-rows[i-1][2]-7*(rows[i][1]-rows[i-1][1])
            self.assertAlmostEqual(pnl, qty*change-fees)
            prev = qty
        db.close()


if __name__ == "__main__":
    unittest.main()
