# 🎓 Flask Course & Class Management System

Một ứng dụng web đơn giản dùng Flask để quản lý khóa học, lớp học và phòng học – dành cho các hệ thống giáo dục cơ bản.

## 🚀 Tính năng chính

- 🔐 Đăng ký & đăng nhập (Phân quyền: Admin, Giáo viên, Học sinh)
- 📚 Quản lý khóa học (Thêm & Xem danh sách)
- 🏫 Quản lý lớp học (Thêm lớp, phân công giáo viên, chỉ định phòng học trống)
- 🏠 Quản lý phòng học (Thêm phòng, theo dõi trạng thái: còn trống / đang sử dụng / bảo trì)
- 👥 Phân quyền giao diện dashboard theo vai trò
- 💬 Tương lai có thể mở rộng để chat realtime (sẵn Flask-SocketIO)

## 🧰 Công nghệ sử dụng

- [Flask](https://flask.palletsprojects.com/) – Web Framework
- [Flask-Login](https://flask-login.readthedocs.io/en/latest/) – Xác thực đăng nhập
- [Flask-SocketIO](https://flask-socketio.readthedocs.io/en/latest/) – Giao tiếp thời gian thực (đã tích hợp, chờ dùng)
- [SQLite](https://www.sqlite.org/index.html) – Cơ sở dữ liệu nhẹ
- [Bootstrap 5](https://getbootstrap.com/) – Giao diện hiện đại, dễ dùng

## 🏗️ Cấu trúc thư mục
├── app.py # Tập tin chính chạy Flask App
├── templates/
│ ├── login.html
│ ├── register.html
│ ├── admin.html
│ ├── add_course.html
│ ├── add_class.html
│ ├── add_room.html
│ ├── view_courses.html
│ ├── view_classes.html
│ └── view_rooms.html
├── static/ # Nơi để CSS tùy chỉnh (nếu có)
└── database.db # Cơ sở dữ liệu SQLite

# Cài môi trường ảo (tùy chọn)
python -m venv venv
source venv/bin/activate  # hoặc .\venv\Scripts\activate trên Windows

# Cài các thư viện cần thiết
pip install flask flask-login flask-socketio

# Chạy ứng dụng
python app.py
👤 Tài khoản mặc định (tự thêm bằng đăng ký)
Bạn có thể tạo tài khoản với vai trò:
admin
teacher
student
