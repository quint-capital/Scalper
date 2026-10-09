import json,urllib.request
from config import TELEGRAM_BOT_TOKEN,TELEGRAM_CHAT_ID
def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:return False
    url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data=json.dumps({"chat_id":TELEGRAM_CHAT_ID,"text":text}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"}),timeout=10) as r:return r.status==200
    except:return False
