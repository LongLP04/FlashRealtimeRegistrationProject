from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret123'
socketio = SocketIO(app)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, full_name, email, role, dob, phone, gender, cccd, password):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.role = role
        self.dob = dob
        self.phone = phone
        self.gender = gender
        self.cccd = cccd
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, role, dob, phone, gender, cccd, password FROM users WHERE id = ?", (user_id,))
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
        cursor.execute("SELECT id, full_name, email, role, dob, phone, gender, cccd, password FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            login_user(User(*user))
            
            return redirect(url_for('dashboard'))
        else:
            flash("Sai tài khoản hoặc mật khẩu!", "danger")
    return render_template('auth/login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    role = current_user.role
    if role == 'admin':
        return render_template('admin/admin.html', user=current_user)
    elif role == 'teacher':
        return render_template('teacher/teacher.html', user=current_user)
    elif role == 'student':
        return render_template('student/student.html', user=current_user)
    else:
        return "Vai trò không xác định", 403

@app.route('/logout')
@login_required
def logout():
     flash("Đăng xuất thành công!", "success")
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
    return render_template('admin/add_room.html')

@app.route('/view-rooms')
@login_required
def view_rooms():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    rooms = cursor.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return render_template('view_rooms.html', rooms=rooms, user =current_user)

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
    return render_template('admin/add_course.html')

@app.route('/view-courses')
@login_required
def view_courses():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    courses = cursor.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template('view_courses.html', courses=courses, user =current_user)

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
    return render_template('admin/add_class.html', courses=courses, teachers=teachers, rooms=rooms)

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
    return render_template('view_classes.html', classes=classes, user = current_user)

@app.route('/view-users')
@login_required
def view_users():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    users = cursor.execute("SELECT id, full_name, email, role FROM users").fetchall()
    conn.close()
    return render_template('admin/view_users.html', users=users)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        #check role trước khi thêm vào dtb
        if role == 'teacher':
            flash ("Không thể đăng ký vai trò giảng viên, liên hệ Admin để được phân quyền.", "danger ")
            return redirect(url_for('register'))


        dob = request.form.get('dob')
        phone = request.form.get('phone')
        gender = request.form.get('gender')
        cccd = request.form.get('cccd')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (full_name, email, password, role, dob, phone, gender, cccd) VALUES (?, ?, ?, ?,?,?,?,?)",
                           (full_name, email, password, role, dob, phone, gender, cccd))
            conn.commit()
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email đã được sử dụng. Vui lòng thử lại.", "danger")
        finally:
            conn.close()

    return render_template('auth/register.html', switch_to_login=False)

@app.route('/update-role/<int:id>', methods=['POST'])
@login_required
def update_role(id):
    if current_user.role != 'admin':
        return "Không có quyền thay đổi vai trò", 403

    new_role = request.form['role']  # Lấy giá trị role từ form

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, id))
        conn.commit()
        flash("Cập nhật vai trò thành công!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Lỗi khi cập nhật vai trò: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('admin/view_users'))  # Quay lại trang danh sách người dùng



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
            role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
            dob DATE,                
            phone TEXT,             
            gender TEXT CHECK (gender IN ('male', 'female', 'other')), 
            cccd TEXT              
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teacher-schedule')
@login_required
def teacher_schedule():
    if current_user.role != 'teacher':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
        SELECT c.id, co.name, s.day_of_week, s.start_time, s.end_time, r.name
        FROM classes c
        JOIN courses co ON c.course_id = co.id
        JOIN schedules s ON s.class_id = c.id
        JOIN rooms r ON c.room_id = r.id
        WHERE c.teacher_id = ?
        ORDER BY s.day_of_week, s.start_time
    """
    result = cursor.execute(query, (current_user.id,)).fetchall()
    conn.close()

    return render_template('teacher/teacher_schedule.html', schedule=result)

@app.route('/register_courses', methods=['POST'])
@login_required
def register_courses():
    # Sử dụng current_user.role thay vì session['role']
    if current_user.role != 'student':
        flash("Chỉ sinh viên mới được đăng ký lớp học", "danger") # Đổi "khóa học" thành "lớp học" cho chính xác với database schema
        return redirect(url_for('view_classes')) # Chuyển hướng về view_classes nếu không phải sinh viên

    class_id = request.form.get('class_id') # Lấy class_id thay vì course_id từ form
    student_id = current_user.id # Sử dụng current_user.id thay vì session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Kiểm tra nếu đã đăng ký lớp học này trước đó trong bảng 'registrations'
        cursor.execute("SELECT * FROM registrations WHERE student_id = ? AND class_id = ?", (student_id, class_id))
        if cursor.fetchone():
            flash("Bạn đã đăng ký lớp học này rồi", "warning")
        else:
            # Kiểm tra xem lớp học còn chỗ trống không
            cursor.execute("SELECT capacity, registered FROM classes WHERE id = ?", (class_id,))
            class_info = cursor.fetchone()

            if class_info:
                capacity = class_info['capacity']
                registered = class_info['registered']

                if registered < capacity:
                    # Thêm đăng ký vào bảng 'registrations'
                    cursor.execute("INSERT INTO registrations (student_id, class_id) VALUES (?, ?)", (student_id, class_id))
                    
                    # Tăng số lượng sinh viên đã đăng ký trong bảng 'classes'
                    cursor.execute("UPDATE classes SET registered = registered + 1 WHERE id = ?", (class_id,))
                    
                    conn.commit()
                    flash("Đăng ký lớp học thành công!", "success")
                else:
                    flash("Lớp học đã đầy, không thể đăng ký thêm.", "danger")
            else:
                flash("Lớp học không tồn tại.", "danger")

    except sqlite3.IntegrityError:
        # Xử lý trường hợp UNIQUE (class_id, student_id) bị vi phạm (đã đăng ký rồi)
        flash("Bạn đã đăng ký lớp học này rồi (lỗi trùng lặp).", "warning")
    except Exception as e:
        conn.rollback() # Hoàn tác các thay đổi nếu có lỗi khác
        flash(f"Lỗi khi đăng ký lớp học: {str(e)}", "danger")
    finally:
        conn.close()

        return redirect(url_for('view_classes')) # Chuyển hướng về trang xem lớp học


@app.route('/update_info', methods=['GET', 'POST'])
@login_required
def update_info():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Retrieve personal information from the form
        full_name = request.form['full_name']
        phone = request.form.get('phone') # Use .get() for optional fields
        dob = request.form.get('dob')
        gender = request.form.get('gender')
        cccd = request.form.get('cccd')

        try:
            # Update personal information in the database
            update_query = """
                UPDATE users
                SET full_name = ?, phone = ?, dob = ?, gender = ?, cccd = ?
                WHERE id = ?
            """
            update_params = (full_name, phone, dob, gender, cccd, current_user.id) # Use current_user.id for the WHERE clause

            cursor.execute(update_query, update_params)
            conn.commit()
            flash("Cập nhật thông tin cá nhân thành công!", "success")

        except sqlite3.Error as e:
            conn.rollback() # Rollback changes if an error occurs
            flash(f"Lỗi khi cập nhật thông tin: {str(e)}", "danger")
        finally:
            conn.close()
            # It's good practice to close the connection in all branches

        # Redirect to the GET route of the same page to show updated info and clear form submission state
        return redirect(url_for('update_info'))

    # For GET request, display the current user information
    # Fetch the latest user data to display in the form
    cursor.execute("SELECT id, full_name, email, role, dob, phone, gender, cccd, password FROM users WHERE id = ?", (current_user.id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        # Create a User object from the fetched data to pass to the template
        # Make sure your User class __init__ can handle all these fields
        user = User(*user_data)
    else:
        # Fallback if user data isn't found (shouldn't happen with @login_required)
        user = current_user
        flash("Không tìm thấy thông tin người dùng.", "danger")


    return render_template("student/information.html", user=user)


# Chạy app
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
