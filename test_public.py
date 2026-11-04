"""Replay a historical forecast using only the observations allowed at decision time."""
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import unittest

from refresh import features, research


class HistoricalReplay(unittest.TestCase):
    def test_forecast_as_of_prior_auction(self):
        db=sqlite3.connect(Path(__file__).parent/"public_results"/"research.sqlite")
        day=date(2026,4,1)
        da,rt,gas,wx={},{},{},{}
        for raw,a,b,g,*w in db.execute("SELECT * FROM inputs"):
            d=date.fromisoformat(raw)
            if d<=day-timedelta(days=10):
                if a is not None: da[d]=a
                if b is not None: rt[d]=b
            if d<=day-timedelta(days=14) and g is not None: gas[d]=g
            if d<=day-timedelta(days=3) and all(v is not None for v in w): wx[d]=w
        _,signal=research(da,rt,gas,wx,day)
        edge,qty=db.execute("SELECT forecast,mwh FROM daily WHERE day=?",(str(day),)).fetchone()
        self.assertAlmostEqual(signal["forecast"],edge)
        self.assertAlmostEqual(signal["target_mwh"],qty)
        del wx[day-timedelta(days=3)]
        self.assertIsNone(features(day,da,rt,gas,wx))
        db.close()


if __name__=="__main__":
    unittest.main()
