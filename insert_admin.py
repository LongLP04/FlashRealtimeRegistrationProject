import sqlite3
from werkzeug.security import generate_password_hash
import os

# Mã hóa mật khẩu
hashed_password = generate_password_hash("Long123@")

# Tạo kết nối tới database
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Tên ảnh mặc định (phải nằm trong thư mục static/images/)
default_avatar = "admin.png"

# Thêm tài khoản admin
try:
    cursor.execute("""
        INSERT INTO users (full_name, email, password, role, dob, phone, gender, cccd, image)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "Admin Test",
        "admin@gmail.com",
        hashed_password,
        "admin",
        "1985-12-15",
        "0123456789",
        "male",
        "123456789012",
        default_avatar
    ))
    conn.commit()
    print("✅ Đã thêm tài khoản admin thành công!")
except sqlite3.IntegrityError:
    print("⚠️  Email admin đã tồn tại trong hệ thống.")
finally:
    conn.close()
