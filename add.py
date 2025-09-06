import os
import json
import gspread
import requests
import re
import datetime
import schedule
import time
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from gspread.exceptions import APIError

# === Configuration (Get from Environment Variables) ===
# We need to load Google Credentials from a string environment variable.
google_credentials_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
line_channel_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# User ID to push notifications. You must replace this with your actual user ID.
USER_ID = "YOUR_LINE_USER_ID"  # REMOVE THIS LINE IN THE REAL CODE

# Make sure all required variables are set
if not all([google_credentials_json_str, line_channel_access_token, line_channel_secret]):
    print("Environment variables are not set correctly!")
    if not google_credentials_json_str:
        print("Missing: GOOGLE_CREDENTIALS_JSON")
    if not line_channel_access_token:
        print("Missing: LINE_CHANNEL_ACCESS_TOKEN")
    if not line_channel_secret:
        print("Missing: LINE_CHANNEL_SECRET")
    exit()

# === Initialize Google Sheets ===
try:
    # Use json.loads to parse the string into a dictionary
    google_credentials = json.loads(google_credentials_json_str)
    gc = gspread.service_account_from_dict(google_credentials)
    spreadsheet = gc.open_by_url('YOUR_SPREADSHEET_URL')  # REMOVE THIS LINE IN THE REAL CODE
    sheet = spreadsheet.get_worksheet(0)
except Exception as e:
    print(f"Failed to initialize Google Sheets client: {e}")
    gc = None
    sheet = None

# === Initialize LINE Bot ===
line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

# === Flask App Setup ===
app = Flask(__name__)

# === LINE Bot Helper Functions ===
def reply_text(reply_token, text):
    """Replies with a single text message."""
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=text))
    except Exception as e:
        print(f"Failed to reply message: {e}")

def push_text(user_id, text):
    """Pushes a single text message to a specific user."""
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=text))
    except Exception as e:
        print(f"Failed to push message: {e}")

# === LINE Bot Webhook Callback ===
@app.route("/callback", methods=['POST'])
def callback():
    """Handles all incoming requests from the LINE platform."""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Check your channel secret.")
        abort(400)
    return 'OK'

# === Message Handler ===
@handler.message(TextMessage)
def handle_message(event):
    """Handles incoming text messages."""
    text = event.message.text.strip()
    replies = []

    # Check for keywords and handle the request
    if text == "สรุปค่าใช้จ่าย":
        try:
            # Check if sheet initialization was successful
            if not sheet:
                reply_text(event.reply_token, "ขออภัย, ไม่สามารถเชื่อมต่อกับ Google Sheets ได้.")
                return

            values = sheet.get_all_values()
            if not values:
                reply_text(event.reply_token, "ยังไม่มีข้อมูลค่าใช้จ่าย.")
                return

            # Skip header row and process data
            total_income = 0
            total_expense = 0
            for row in values[1:]:
                if len(row) >= 3:
                    amount = float(row[1])
                    if row[2] == 'รายรับ':
                        total_income += amount
                    elif row[2] == 'รายจ่าย':
                        total_expense += amount

            balance = total_income - total_expense
            summary = f"สรุปค่าใช้จ่าย:\nรายรับ: {total_income} บาท\nรายจ่าย: {total_expense} บาท\nยอดคงเหลือ: {balance} บาท"
            replies.append(summary)

        except APIError as e:
            replies.append("ขออภัย, มีข้อผิดพลาดในการเข้าถึง Google Sheets.")
            print(f"Google Sheets API Error: {e}")
        except Exception as e:
            replies.append("ขออภัย, เกิดข้อผิดพลาดบางอย่าง.")
            print(f"Unexpected error: {e}")

    elif text.lower().startswith('รายรับ'):
        # ... (rest of your existing logic for income)
        pass # Placeholder for your existing logic
        
    elif text.lower().startswith('รายจ่าย'):
        # ... (rest of your existing logic for expense)
        pass # Placeholder for your existing logic
    
    else:
        replies.append("สวัสดีครับ! ผมเป็นบอทสำหรับบันทึกรายรับ-รายจ่ายครับ\n\nตัวอย่างการใช้งาน:\n- รายรับ 500\n- รายจ่าย 150\n- สรุปค่าใช้จ่าย")
    
    # Send a single reply message to avoid RecursionError
    if replies:
        reply_text(event.reply_token, "\n\n".join(replies))
        
# The scheduled tasks are not executed in the Gunicorn worker process.
# We will disable this section as it is not needed for the web service.
# ======================== RUN SCHEDULE IN BACKGROUND ========================
# def run_schedule():
#     schedule.every().day.at("21:00").do(send_daily_summary)
#     schedule.every().sunday.at("21:05").do(send_weekly_summary)
#     schedule.every().day.at("21:10").do(auto_backup_csv)
#     while True:
#         schedule.run_pending()
#         time.sleep(60)
# ============================================================================

if __name__ == '__main__':
    # This part is for local testing. In production, Gunicorn will run the app.
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
