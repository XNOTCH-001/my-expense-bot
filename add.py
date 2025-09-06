import os
import datetime
import threading
import schedule
import time
import csv
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# ================= LINE BOT CONFIG =================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
USER_ID = os.environ.get("USER_ID")

# ตรวจสอบว่ามีค่า LINE Token และ Secret หรือไม่
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET not found in environment variables.")
    # คุณสามารถเพิ่มโค้ดสำหรับจัดการกรณีที่ไม่มีค่าเหล่านี้ได้ที่นี่
else:
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(LINE_CHANNEL_SECRET)


# ================= GOOGLE SHEETS CONFIG =================
# แก้ไขโค้ดส่วนนี้เพื่อดึงข้อมูลรับรองจาก Environment Variable เพื่อความปลอดภัย
sheet = None
try:
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        creds_info = json.loads(credentials_json)
        SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
        gc = gspread.authorize(creds)
        sheet = gc.open("ExpenseTracker").sheet1
    else:
        print("Error: GOOGLE_CREDENTIALS_JSON not found in environment variables.")
except Exception as e:
    print(f"Failed to initialize Google Sheets client: {e}")
    
# ================= PARAMETERS =================
THRESHOLD = 500

# ================= HELPER FUNCTION =================
def reply_text(reply_token, text):
    line_bot_api.reply_message(reply_token, TextSendMessage(text=text))

def push_text(user_id, text):
    line_bot_api.push_message(user_id, TextSendMessage(text=text))

# ================= LINE CALLBACK =================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ================= HANDLE MESSAGE =================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if sheet is None:
        reply_text(event.reply_token, "❌ ไม่สามารถเชื่อมต่อกับ Google Sheets ได้ โปรดตรวจสอบการตั้งค่า")
        return

    text = event.message.text.strip()
    
    # เช็คยอดคงเหลือ
    if text.lower() == "ยอดคงเหลือ":
        values = sheet.get_all_values()
        balance = int(values[-1][4]) if len(values) > 1 and values[-1][4].isdigit() else 0
        reply_text(event.reply_token, f"💰 ยอดคงเหลือปัจจุบัน: {balance} บาท")
        return

    # ส่งข้อความหลายบรรทัด
    lines = text.split("\n")
    replies = []

    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            tran_type, item, amount_str = parts[0], parts[1], parts[2]
            category = parts[3] if len(parts) >= 4 else "-"
            try:
                amount = int(amount_str)
            except ValueError:
                replies.append(f"❌ จำนวนเงินไม่ถูกต้อง: {line}")
                continue

            date_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            values = sheet.get_all_values()
            balance = int(values[-1][4]) if len(values) > 1 and values[-1][4].isdigit() else 0

            if tran_type == "รับ":
                balance += amount
            elif tran_type == "จ่าย":
                balance -= amount
            else:
                replies.append(f"❌ ใช้คำว่า 'รับ' หรือ 'จ่าย' เท่านั้น: {line}")
                continue

            sheet.append_row([date_time, tran_type, item, amount, balance, category])
            replies.append(f"✅ บันทึกแล้ว: {tran_type} {item} {amount} บาท [{category}]\nยอดคงเหลือ: {balance} บาท")

            if balance < THRESHOLD and USER_ID:
                push_text(USER_ID, f"⚠️ ยอดคงเหลือต่ำกว่า {THRESHOLD} บาท! ยอดปัจจุบัน: {balance} บาท")
        else:
            replies.append(f"❌ รูปแบบไม่ถูกต้อง: {line}\nตัวอย่าง: จ่าย ข้าว 50 อาหาร")

    if replies:
        reply_text(event.reply_token, "\n\n".join(replies))

# ================= SCHEDULE FUNCTIONS =================
def send_daily_summary():
    if sheet is None:
        print("Scheduler: Cannot send daily summary. Sheet is not initialized.")
        return
    values = sheet.get_all_values()
    today = datetime.datetime.now().strftime("%d/%m/%Y")
    income = sum(int(r[3]) for r in values[1:] if r[0].startswith(today) and r[1] == "รับ" and r[3].isdigit())
    expense = sum(int(r[3]) for r in values[1:] if r[0].startswith(today) and r[1] == "จ่าย" and r[3].isdigit())
    balance = int(values[-1][4]) if len(values) > 1 and values[-1][4].isdigit() else 0
    summary = f"📊 สรุปประจำวัน {today}\nรับ: {income} บาท\nจ่าย: {expense} บาท\nคงเหลือ: {balance} บาท"
    if USER_ID:
        push_text(USER_ID, summary)

def send_weekly_summary():
    if sheet is None:
        print("Scheduler: Cannot send weekly summary. Sheet is not initialized.")
        return
    values = sheet.get_all_values()
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=7)
    
    income = sum(int(r[3]) for r in values[1:] if datetime.datetime.strptime(r[0].split()[0], "%d/%m/%Y") >= start_date and r[1] == "รับ" and r[3].isdigit())
    expense = sum(int(r[3]) for r in values[1:] if datetime.datetime.strptime(r[0].split()[0], "%d/%m/%Y") >= start_date and r[1] == "จ่าย" and r[3].isdigit())
    balance = int(values[-1][4]) if len(values) > 1 and values[-1][4].isdigit() else 0
    
    summary = f"📊 สรุปรายสัปดาห์ ({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')})\nรับ: {income} บาท\nจ่าย: {expense} บาท\nคงเหลือ: {balance} บาท"
    if USER_ID:
        push_text(USER_ID, summary)

def auto_backup_csv():
    if sheet is None:
        print("Scheduler: Cannot create backup. Sheet is not initialized.")
        return
    values = sheet.get_all_values()
    filename = f"Expense_Backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(values)
    if USER_ID:
        push_text(USER_ID, f"📁 สำรองข้อมูลอัตโนมัติ: {filename}")

# ================= RUN SCHEDULE IN BACKGROUND =================
def run_schedule():
    schedule.every().day.at("21:00").do(send_daily_summary)
    schedule.every().sunday.at("21:05").do(send_weekly_summary)
    schedule.every().day.at("21:10").do(auto_backup_csv)
    while True:
        schedule.run_pending()
        time.sleep(60)

# ================= MAIN =================
if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # ตรวจสอบว่า sheet ถูกสร้างขึ้นสำเร็จก่อนที่จะรัน Scheduler
        if sheet is not None:
            t = threading.Thread(target=run_schedule, daemon=True)
            t.start()
        else:
            print("Scheduler will not run because Google Sheets client is not initialized.")
    app.run(port=5000, debug=True)
