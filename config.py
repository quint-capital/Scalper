import os

DERIV_SYMBOL = os.getenv("DERIV_SYMBOL", "R_75").strip()
HISTORY_FILE = os.getenv("HISTORY_FILE", "/app/data/qute_adaptive_v75_history.json")
MAX_M1_HISTORY = int(os.getenv("MAX_M1_HISTORY", "30000"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Preserve the WebSocket endpoints from the user's known-working v3.5 package.
# Only override the primary endpoint explicitly through DERIV_WS_URL if needed.
WS_URLS = [
    os.getenv("DERIV_WS_URL", "wss://api.derivws.com/trading/v1/options/ws/public").strip(),
    "wss://ws.binaryws.com/websockets/v3",
]

# Deep bootstrap: enough M1 data to create meaningful H4/H1/M30/M15/M5 context.
HISTORY_BOOTSTRAP_CANDLES = int(os.getenv("HISTORY_BOOTSTRAP_CANDLES", "10000"))
HISTORY_BATCH_SIZE = int(os.getenv("HISTORY_BATCH_SIZE", "1000"))

# Persistent analysis/outcome journal (stored on the Railway volume).
ANALYSIS_JOURNAL_FILE = os.getenv("ANALYSIS_JOURNAL_FILE", "/app/data/qute_adaptive_analysis_v1.jsonl")
SETUP_JOURNAL_FILE = os.getenv("SETUP_JOURNAL_FILE", "/app/data/qute_adaptive_setups_v1.json")
ACTIVE_SETUPS_FILE = os.getenv("ACTIVE_SETUPS_FILE", "/app/data/qute_adaptive_active_v1.json")
MAX_ANALYSIS_JOURNAL_BYTES = int(os.getenv("MAX_ANALYSIS_JOURNAL_BYTES", str(25 * 1024 * 1024)))
MAX_SETUP_HISTORY = int(os.getenv("MAX_SETUP_HISTORY", "5000"))

# Runtime storage diagnostics. Railway must mount its persistent Volume at /app/data
# (or explicitly override the *_FILE variables above).
DATA_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app/data").strip() or "/app/data"
STORAGE_MARKER_FILE = os.getenv("STORAGE_MARKER_FILE", "/app/data/.quint_v75_adaptive_volume_marker")

# Independent adaptive-learning journals. Keep all filenames distinct from baseline.
LEARNING_ACTIVE_FILE = os.getenv("LEARNING_ACTIVE_FILE", "/app/data/qute_adaptive_shadow_active_v1.json")
LEARNING_HISTORY_FILE = os.getenv("LEARNING_HISTORY_FILE", "/app/data/qute_adaptive_shadow_history_v1.json")
LEARNING_MODEL_FILE = os.getenv("LEARNING_MODEL_FILE", "/app/data/qute_adaptive_model_v1.json")
LEARNING_MIN_RESOLVED = int(os.getenv("LEARNING_MIN_RESOLVED", "30"))
LEARNING_MIN_GROUP_SAMPLES = int(os.getenv("LEARNING_MIN_GROUP_SAMPLES", "12"))
LEARNING_MIN_BAD_GROUPS = int(os.getenv("LEARNING_MIN_BAD_GROUPS", "2"))
LEARNING_CONFIDENCE_Z = float(os.getenv("LEARNING_CONFIDENCE_Z", "1.28"))
LEARNING_MAX_SHADOW_HISTORY = int(os.getenv("LEARNING_MAX_SHADOW_HISTORY", "5000"))
