import os

DERIV_SYMBOL = os.getenv("DERIV_SYMBOL", "R_75").strip()
HISTORY_FILE = os.getenv("HISTORY_FILE", "/app/data/v75_history.json")
MAX_M1_HISTORY = int(os.getenv("MAX_M1_HISTORY", "30000"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

WS_URLS = [
    os.getenv("DERIV_WS_URL", "wss://ws.derivws.com/websockets/v3?app_id=1089").strip(),
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
]

# Deep bootstrap: enough M1 data to create meaningful H4/H1/M30/M15/M5 context.
HISTORY_BOOTSTRAP_CANDLES = int(os.getenv("HISTORY_BOOTSTRAP_CANDLES", "10000"))
HISTORY_BATCH_SIZE = int(os.getenv("HISTORY_BATCH_SIZE", "1000"))

# Persistent analysis/outcome journal (stored on the Railway volume).
ANALYSIS_JOURNAL_FILE = os.getenv("ANALYSIS_JOURNAL_FILE", "/app/data/v75_scalp_analysis.jsonl")
SETUP_JOURNAL_FILE = os.getenv("SETUP_JOURNAL_FILE", "/app/data/v75_scalp_setups.json")
ACTIVE_SETUPS_FILE = os.getenv("ACTIVE_SETUPS_FILE", "/app/data/v75_scalp_active.json")
MAX_ANALYSIS_JOURNAL_BYTES = int(os.getenv("MAX_ANALYSIS_JOURNAL_BYTES", str(25 * 1024 * 1024)))
MAX_SETUP_HISTORY = int(os.getenv("MAX_SETUP_HISTORY", "5000"))

# Runtime storage diagnostics. Railway must mount its persistent Volume at /app/data
# (or explicitly override the *_FILE variables above).
DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app/data").strip() or "/app/data"
STORAGE_MARKER_FILE = os.getenv("STORAGE_MARKER_FILE", "/app/data/.quint_v75_volume_marker")
