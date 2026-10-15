# Double-reversed baseline paper experiment

- The uploaded QUTE version already inverted each source BUY/SELL signal and swapped source SL with source TP1.
- This version reverses that transformation a second time: it restores the source direction and source SL/TP1 geometry.
- TP1 remains the only take-profit; TP2/TP3 are not used.
- This is paper analysis only and does not send broker orders.
- Because the second reversal mathematically undoes the first, this should be compared against the inverse log on matched signal/candle paths; it is not expected to create a new independent edge.
