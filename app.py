from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret123'
socketio = SocketIO(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, full_name, email, role):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(*row)
    return None

# ROUTES
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, email, role FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            login_user(User(*user))
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Sai tài khoản hoặc mật khẩu!", "danger")
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role
    if role == 'admin':
        return render_template('admin.html', user=current_user)
    elif role == 'teacher':
        return render_template('teacher.html', user=current_user)
    elif role == 'student':
        return render_template('student.html', user=current_user)
    else:
        return "Vai trò không xác định", 403

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add-room', methods=['GET', 'POST'])
@login_required
def add_room():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    if request.method == 'POST':
        name = request.form['name']
        status = request.form['status']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO rooms (name, status) VALUES (?, ?)", (name, status))
        conn.commit()
        conn.close()
        flash("Đã thêm phòng học thành công!", "success")
        return redirect(url_for('dashboard'))
    return render_template('add_room.html')

@app.route('/view-rooms')
@login_required
def view_rooms():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    rooms = cursor.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return render_template('view_rooms.html', rooms=rooms)

@app.route('/add-course', methods=['GET', 'POST'])
@login_required
def add_course():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO courses (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        conn.close()
        flash("Đã thêm khóa học!", "success")
        return redirect(url_for('dashboard'))
    return render_template('add_course.html')

@app.route('/view-courses')
@login_required
def view_courses():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    courses = cursor.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template('view_courses.html', courses=courses)

@app.route('/add-class', methods=['GET', 'POST'])
@login_required
def add_class():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    courses = cursor.execute("SELECT id, name FROM courses").fetchall()
    teachers = cursor.execute("SELECT id, full_name FROM users WHERE role = 'teacher'").fetchall()
    rooms = cursor.execute("SELECT id, name FROM rooms WHERE status = 'available'").fetchall()

    if request.method == 'POST':
        course_id = request.form['course_id']
        teacher_id = request.form['teacher_id']
        room_id = request.form['room_id']
        capacity = request.form['capacity']

        cursor.execute("INSERT INTO classes (course_id, teacher_id, room_id, capacity) VALUES (?, ?, ?, ?)",
                       (course_id, teacher_id, room_id, capacity))

        cursor.execute("UPDATE rooms SET status = 'occupied' WHERE id = ?", (room_id,))

        conn.commit()
        conn.close()
        flash("Đã tạo lớp học thành công!", "success")
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('add_class.html', courses=courses, teachers=teachers, rooms=rooms)

@app.route('/view-classes')
@login_required
def view_classes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    query = """
        SELECT classes.id, courses.name, users.full_name, rooms.name, classes.capacity, classes.registered
        FROM classes
        JOIN courses ON classes.course_id = courses.id
        JOIN users ON classes.teacher_id = users.id
        JOIN rooms ON classes.room_id = rooms.id
    """
    classes = cursor.execute(query).fetchall()
    conn.close()
    return render_template('view_classes.html', classes=classes)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (full_name, email, password, role) VALUES (?, ?, ?, ?)",
                           (full_name, email, password, role))
            conn.commit()
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email đã được sử dụng. Vui lòng thử lại.", "danger")
        finally:
            conn.close()

    return render_template('register.html')

# Khởi tạo cơ sở dữ liệu

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ('available', 'occupied', 'maintenance'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            capacity INTEGER NOT NULL CHECK (capacity > 0),
            registered INTEGER DEFAULT 0,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (teacher_id) REFERENCES users(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            register_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            UNIQUE (class_id, student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL CHECK (day_of_week IN ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
    """)

    conn.commit()
    conn.close()

# Chạy app
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
