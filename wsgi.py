# ไฟล์นี้ทำหน้าที่เป็นจุดเริ่มต้นของแอปพลิเคชันสำหรับ Gunicorn
# Gunicorn จะเรียกใช้ 'application' ที่ถูกกำหนดไว้ในไฟล์นี้
import sys
# แก้ไขจาก 'app' เป็น 'add' เพื่อให้เรียกใช้ไฟล์ add.py
from add import app as application