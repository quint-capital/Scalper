# Quint Capital V75 Research Engine v1.2

Analysis only. No trade execution, account authorization, or order placement.

## Included files
- `main.py`: complete single-file system: historical M1 candle downloader, strategy research/backtest, CSV/JSON reporting, daily backtest marker, and public tick monitor.
- `requirements.txt`: WebSocket dependency.
- `railway.json`: Railway start command and restart policy.

## Deploy
1. Upload/replace these files in the GitHub repository root.
2. Keep `requirements.txt` as supplied.
3. Railway should start with `python -u main.py` from `railway.json`.
4. Set Railway variable `BACKTEST_DAYS=7` (optional; default is 7). `BACKTEST_MIN_INTERVAL_HOURS` defaults to 24. `DATA_DIR` defaults to `/app/data`; attach your existing persistent volume there.
5. Do not delete the existing persistent volume.

## Output
Reports are written under `/app/data/backtests` by default: M1 history CSV, strategy results CSV, and JSON summary. Existing files are not intentionally deleted.

## Important limitations
- The code uses Deriv public WebSocket endpoints and cannot guarantee they are reachable from Railway. HTTP 520 must be diagnosed from deployment logs; changing the backtest length does not fix network/endpoint errors.
- No successful live connection or historical download is claimed until Railway logs show candle retrieval and a completed report.
- Cost deductions are illustrative sensitivity scenarios, not measured spreads/slippage. Backtest outcomes are research, not a guarantee of future performance.
