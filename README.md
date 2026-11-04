# ERCOT North power trading research

[Read the one-page trading memo](artifacts/ERCOT%20North%20Trading%20Memo.pdf) | [Download the Excel workbook](artifacts/Spark%20Spread.xlsx)

This project tests whether gas economics and weather help forecast the ERCOT North day-ahead versus real-time premium. Over 669 held-out delivery days, the weather model lost $36,295 after assumed costs. The short benchmark earned $37,912, including $40,799 on a single day.

The live research pipeline is Python and SQLite. The tools directory also contains the original presentation builders. The memo builder uses ReportLab and Windows Segoe UI fonts. The workbook builder uses Node.js and @oai/artifact-tool. Run builders from the repository root.

## Project guide

The public-data strategy downloads observed ERCOT North day-ahead and real-time prices, Henry Hub gas and Dallas–Fort Worth airport weather. The earlier synthetic spark-spread exercise is included separately in the results folder.

## Start the public market dashboard

Extract the ZIP and open a terminal in the folder containing refresh.py. Python 3.10 or newer is required.

~~~sh
python -m pip install -r requirements.txt
python refresh.py --watch
~~~

Open **public_results/dashboard.html** in a browser. A saved run is included so you can inspect it immediately. The command checks the public feeds hourly while running. The page rereads the local report every two minutes. Stop with Ctrl+C. For a single update, use `python refresh.py`. Annual ERCOT documents are cached by version ID. A new document triggers a fresh import. Network or feed failures keep the last report and its original timestamp. The Excel Public markets tab is a snapshot. Refresh writes a new daily.csv and research.sqlite for further analysis.

## What the public strategy trades

For each ERCOT operating day D the model forecasts the **real-time average minus the day-ahead average** at HB_NORTH, in USD/MWh. A positive forecast above $1 buys day-ahead and sells real-time. A negative forecast below −$1 sells day-ahead and buys real-time. Otherwise it stays flat. Henry Hub enters the spark-spread feature. This strategy's cash flows come from the two power settlements. Total MWh is spread evenly across the operating day's hours, including daylight-saving transitions.

**Forecast = training intercept + sum of standardized factor values × fitted coefficients.** The eight inputs are a seven-day average power price less seven times Henry Hub gas, the seven-day North Hub RT-minus-DA premium, its 14-day volatility, the delivery-weekend indicator, cooling and heating degrees relative to 65°F, wind speed, and relative humidity. Weather is observed at DFW. Cooling and heating use the midpoint of the high and low temperature. Load sensitivity is represented indirectly by weather. The no-weather control refits on the first four inputs.

The regression refits each delivery day on 180 eligible completed examples. All centering, scaling and target clipping (5th and 95th percentile order statistics) use the training window. Ridge penalty is 9. Holdout scoring starts January 1, 2025. Realized test returns retain every price spike. To approximate publication delays, settlement features and training labels stop at D−10, weather uses D−3, and gas uses the most recent quote dated D−14 to D−21. Historical revisions can differ from the original releases. The input database contains the downloaded vintage. Each additional refresh records the first available future signal per delivery date in paper_journal.sqlite and later scores it against the published settlements.

Position magnitude is the lesser of 100 MWh and $350 divided by the standard deviation of the last 30 eligible training outcomes. Daily net P&L equals signed MWh times the realized premium less $1 per absolute MWh. No position carries across delivery days. Risk-matched always-long and always-short controls each pay the same round-trip cost. The short control was added after seeing the long-control result. Evaluate it prospectively before drawing conclusions about repeatability. All results assume full clearing and omit collateral, uplift, market access costs and participant-specific fees.

The latest target is tomorrow before 10 a.m. Central and the following day afterward. Missing required dates suppress the signal. A signed quantity of zero means flat. The timestamp on the dashboard is the last completed refresh.

**Public sources.** [ERCOT settlement archives](https://www.ercot.com/mktinfo/prices), [EIA Henry Hub via FRED](https://fred.stlouisfed.org/series/DHHNGSP), and [Iowa Environmental Mesonet daily observations](https://mesonet.agron.iastate.edu/request/daily.phtml?network=TX_ASOS). Exact download URLs, publication dates where provided, and feed coverage appear in public_results/status.json.

## Run the original synthetic example

Extract the ZIP, open a terminal in the extracted directory and run the following with Python 3.10 or newer. The model uses the standard library.

~~~sh
python model.py
python model.py --csv results/market.csv --out replay --heat-rate 7 --variable-om 3 --size-mwh 100 --fee 0.15
~~~

The first command reproduces the included results. The second replays the sample CSV and writes to a separate folder. Each run replaces market.sqlite, market.csv and ledger.csv in the selected output directory. Open market.sqlite in a SQLite viewer to query market, settings, economics and ledger.

~~~sql
SELECT day, signal, position, spread, fees, net_pnl, equity, drawdown
FROM ledger
ORDER BY drawdown LIMIT 10;
~~~

## Use market data

Supply a UTF-8 CSV with these exact headers, in order. Use one row per common observation date, oldest first. Weekends and gaps are allowed. Lags and lookbacks count rows. Align inputs before import and keep at least 23 rows.

| Field | Definition |
|---|---|
| day | ISO delivery date, YYYY-MM-DD |
| gas | Henry Hub spot price in USD/MMBtu, strictly positive |
| power | ERCOT HB_NORTH day-ahead price in USD/MWh, mean of all hours for that operating day |
| temp | Daily average temperature in degrees Fahrenheit for a consistent Texas station or regional series |
| load | ERCOT system daily average demand in MW, strictly positive |

Historical sources include [ERCOT day-ahead hub settlements](https://www.ercot.com/mp/data-products/data-product-details?id=NP4-180-ER) and [EIA Henry Hub spot prices](https://www.eia.gov/dnav/ng/hist/rngwhhdD.htm). Preserve repeated daylight-saving hours in the daily power average. Join observations to dates with an available gas mark and verify publication times before reusing a signal. The included generator uses a seasonal temperature series, temperature-sensitive load, a mean-reverting gas price and a load-linked power premium.

## Economics and strategy

Fuel cost per MWh equals the gas price times plant heat rate. Gross spark spread equals power price less fuel cost. Dividing power by gas gives the implied heat rate. Subtracting variable O&M from the spread gives generation margin before fixed costs. The [EIA spread definition](https://www.eia.gov/todayinenergy/includes/sparkspread_explain.php) describes the underlying convention.

Each end-of-day signal compares load, absolute temperature deviation from 65°F, and spread with their respective means over the preceding 20 observations. When load and temperature deviation are both above their means and the spread is below its mean, target a long spread. Reverse all three conditions for a short. Otherwise target zero. Ties are flat. This rule tests whether a cheap spread recovers when weather and demand indicate pressure on the grid.

A signal formed on observation t is assumed filled at the mark on t+1. It first earns the mark change from t+1 to t+2. Position +1 represents long 100 MWh power and short 700 MMBtu gas at default settings. The short position reverses both legs. Daily P&L equals held position times size times the spread change, less the combined fee on absolute position changes. A reversal incurs two turns. The ledger assigns entry and rebalancing fees to the earning interval and liquidates the last holding at the final mark. The always-long comparator begins on the same first eligible interval. Drawdown is cumulative net P&L minus its running peak, including a starting peak of zero.

Daily spot averages are proxy marks for a hypothetical paired position. Daily delivery products differ across dates. Actual fills, contract rolls, margin, local fuel basis, transmission congestion and plant start costs require additional modeling. Variable O&M affects generator margin only. The trading leg tracks the gross spread.

## Excel

The Walk-forward sheet shows the Python run delivered with the workbook. Its daily positions and P&L are a fixed snapshot. The summary formulas aggregate that snapshot. The editable Overview assumptions drive the Daily strategy.

## Walk-forward forecast and risk

The forecast estimates the spread change between the next two marks using current spread, load and absolute temperature deviation from 65°F. Each ridge regression uses the most recent 90 completed feature/target pairs. Centering and scaling use only that training window. The intercept is unpenalized. The ridge penalty is 9 on the sum-of-squares objective. Each fitted model serves the next 20 signal dates. The CSV records the last observed training label and coefficients in dollars per MWh per training-window standard deviation.

A trade requires a forecast magnitude greater than two one-way fees per MWh. Signed size equals the lesser of the position cap and the daily dollar risk budget divided by the trailing 20-observation sample standard deviation of spread changes. The strategy stays flat at zero volatility. Use `--risk-budget 250` to change the default $350 budget. The budget targets one standard deviation of daily P&L. Realized losses can exceed it.

The walk-forward ledger starts at the first eligible earning interval and charges turnover-based fees on fractional positions, including final liquidation. Its always-long comparison uses the same evaluation dates and the full MWh cap. Short inputs still run the original strategy; at least 94 observations are needed for one walk-forward P&L. The worst-tail mean averages the lowest 5% of daily net P&Ls, rounding the count up. Query forecasts, walkforward and risk in SQLite or inspect their CSV exports.

## Workbook inputs

Overview compares both strategies and shows the last day's generation margin under additive power and gas shocks. Edit a blue driver to recalculate. For example, at a heat rate of 7, raising gas by $0.50/MMBtu at fixed power reduces margin by $3.50/MWh. Daily contains the complete formula ledger. To examine different data of the same length, replace the 365 rows in Daily A5:E369 with aligned dates and numeric inputs and update the two source captions. Use Python for other panel lengths. Excel and SQLite run independently.

