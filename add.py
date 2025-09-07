import os
import json
import re
from datetime import datetime, timedelta

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import gspread
from google.oauth2.service_account import Credentials

# ==============================
# LINE Config
# ==============================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
USER_ID = os.environ.get("USER_ID")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==============================
# Google Sheets Config
# ==============================
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")  # เก็บ Spreadsheet ID ใน Env ด้วย

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# โหลด credentials จาก Environment Variable
creds_json = os.environ.get("GOOGLE_CREDENTIALS")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

# ==============================
# Flask App
# ==============================
app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ==============================
# Helper Functions
# ==============================
def add_transaction(t_type, item, amount):
    balance = int(worksheet.cell(worksheet.row_count, 4).value or 0)

    if t_type == "จ่าย":
        balance -= amount
    elif t_type == "รับ":
        balance += amount

    worksheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        t_type,
        item,
        amount,
        balance
    ])

    return balance

# ==============================
# LINE Message Handler
# ==============================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    # รองรับหลายบรรทัด
    lines = text.split("\n")
    responses = []

    for line in lines:
        match = re.match(r"^(จ่าย|รับ)\s+(.+)\s+(\d+)$", line)
        if match:
            t_type, item, amount = match.groups()
            amount = int(amount)
            balance = add_transaction(t_type, item, amount)
            responses.append(f"{t_type} {item} {amount} บาท\nยอดคงเหลือ: {balance} บาท")
        elif line == "ยอด":
            balance = worksheet.cell(worksheet.row_count, 4).value
            responses.append(f"ยอดคงเหลือปัจจุบัน: {balance} บาท")
        else:
            responses.append("❌ รูปแบบไม่ถูกต้อง\nตัวอย่าง: \n- จ่าย ข้าว 50\n- รับ เงินเดือน 10000")

    reply = "\n\n".join(responses)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# ==============================
# Main
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))