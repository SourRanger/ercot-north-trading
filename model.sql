CREATE TABLE market(day TEXT PRIMARY KEY, gas REAL, power REAL, temp REAL, load REAL);
CREATE TABLE settings(heat_rate REAL, variable_om REAL, size_mwh REAL, fee REAL, source TEXT);

CREATE VIEW economics AS
SELECT m.*, gas * heat_rate AS fuel, power - gas * heat_rate AS spread,
       power / gas AS implied_hr, power - gas * heat_rate - variable_om AS margin,
       abs(temp - 65) AS thermal_stress
FROM market m CROSS JOIN settings;

CREATE TABLE ledger AS
WITH history AS (
  SELECT *, avg(spread) OVER prior AS avg_spread, avg(load) OVER prior AS avg_load,
         avg(thermal_stress) OVER prior AS avg_stress, count(*) OVER prior AS observations
  FROM economics WINDOW prior AS (ORDER BY day ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
), signals AS (
  SELECT *, CASE WHEN observations < 20 THEN 0
    WHEN load > avg_load AND thermal_stress > avg_stress AND spread < avg_spread THEN 1
    WHEN load < avg_load AND thermal_stress < avg_stress AND spread > avg_spread THEN -1
    ELSE 0 END AS signal FROM history
), positions AS (
  SELECT *, lag(signal, 2, 0) OVER w AS position,
         CASE WHEN lag(observations,2,0) OVER w = 20 THEN 1 ELSE 0 END AS benchmark,
         spread - lag(spread,1,spread) OVER w AS spread_change,
         lead(day) OVER w IS NULL AS last_day
  FROM signals WINDOW w AS (ORDER BY day)
), trades AS (
  SELECT *, abs(position - lag(position,1,0) OVER w) + last_day * abs(position) AS turnover,
         abs(benchmark - lag(benchmark,1,0) OVER w) + last_day * benchmark AS bench_turn
  FROM positions WINDOW w AS (ORDER BY day)
), earnings AS (
  SELECT t.*, position * size_mwh * spread_change AS gross_pnl, turnover * size_mwh * fee AS fees,
         size_mwh * (benchmark * spread_change - bench_turn * fee) AS bench_pnl
  FROM trades t CROSS JOIN settings
), curve AS (
  SELECT *, gross_pnl - fees AS net_pnl, sum(gross_pnl - fees) OVER w AS equity,
         sum(bench_pnl) OVER w AS bench_equity
  FROM earnings WINDOW w AS (ORDER BY day ROWS UNBOUNDED PRECEDING)
)
SELECT *, equity - max(0, max(equity) OVER w) AS drawdown,
       bench_equity - max(0, max(bench_equity) OVER w) AS bench_drawdown
FROM curve WINDOW w AS (ORDER BY day ROWS UNBOUNDED PRECEDING) ORDER BY day;
