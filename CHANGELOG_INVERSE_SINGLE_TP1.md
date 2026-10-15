# Inverse signal + single TP1 variant

- BUY setups are inverted to SELL; SELL setups are inverted to BUY.
- The original setup's SL is used as the inverse TP1.
- The original setup's TP1 is used as the inverse SL.
- TP2/TP3 and RR fields are removed from the inverse setup/report/journal.
- The source TP1 minimum-RR rejection was removed; a valid structural TP1 is retained even if close. If no usable opposing pivot exists, the source TP1 fallback is 0.50 times source risk.
- Inverse setup history, active setups, and analysis journal use separate `/app/data/v75_inverse_*` files to avoid mixing with original records.
- This is paper analysis only; no broker orders are placed.
- Same-candle SL/TP1 touches remain marked ambiguous because M1 OHLC cannot establish intrabar order.
