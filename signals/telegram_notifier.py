import requests, os

def notify(msg):
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    data = {"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": msg}
    requests.post(url, data=data)