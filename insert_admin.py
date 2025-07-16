import sqlite3

# Thêm tài khoản admin
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO users (full_name, email, password, role, dob, phone, gender, cccd)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ("Admin Test", "admin1@gmail.com", "Long123@", "admin", "1985-12-15", "0123456789", "male", "123456789012"))

# Commit và đóng kết nối
conn.commit()
conn.close()

print("✅ Đã thêm tài khoản admin thành công!")
