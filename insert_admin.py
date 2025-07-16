import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO users (full_name, email, password, role)
    VALUES (?, ?, ?, ?)
""", ("Admin Test", "admin1@gmail.com", "TramAnh123@", "admin"))

conn.commit()
conn.close()

print("✅ Đã thêm tài khoản admin thành công!")
