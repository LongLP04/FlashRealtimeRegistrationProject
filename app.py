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

# Dăng nhập, đăng xuất
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


# Xem danh sách phòng học, thêm, sửa, xóa
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
    return render_template('admin/add_room.html',user =current_user)
@app.route('/view-rooms')
@login_required
def view_rooms():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    query = """
        select r.id, r.name, r.status, co.name as course_name, u.full_name as teacher_name
        from rooms r
        left join classes c on r.id = c.room_id
        left join courses co on c.course_id = co.id
        left join users u on c.teacher_id = u.id
        group by r.id
    """
    rooms = cursor.execute(query).fetchall()
    conn.close()
    return render_template('view_rooms.html', rooms=rooms, user =current_user)
@app.route('/delete-room/<int:room_id>', methods=['POST'])
@login_required
def delete_room(room_id):
    if current_user.role != 'admin':
        return 'Không có quyền truy cập', 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Kiểm tra xem phòng có đang được sử dụng trong lớp học nào không
        cursor.execute("SELECT COUNT(*) FROM classes WHERE room_id = ?", (room_id,))
        count = cursor.fetchone()[0]

        if count > 0:
            flash("Không thể xóa: Phòng này đang được sử dụng trong lớp học!", "warning")
        else:
            cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            conn.commit()
            flash("Đã xóa phòng học thành công!", "success")

    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Lỗi khi xóa phòng học: {str(e)}", "danger")

    finally:
        conn.close()

    return redirect(url_for('view_rooms'))

@app.route('/edit-room/<int:room_id>', methods=['POST', 'GET'])
@login_required
def edit_room(room_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        status = request.form['status']
        cursor.execute('UPDATE rooms SET name = ?, status = ? WHERE id = ?', (name, status, room_id))
        conn.commit()
        conn.close()
        flash("Đã cập nhật phòng học thành công!", "success")
        return redirect(url_for('view_rooms'))
    else:
        cursor.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        conn.close()
        if room:
            return render_template('admin/edit_room.html', room=room, user=current_user)
        else:
            flash("Phòng học không tồn tại!", "danger")
            return redirect(url_for('view_rooms'))
        

# Thêm khóa học, xem danh sách khóa học
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
    return render_template('admin/add_course.html', user=current_user)

@app.route('/view-courses')
@login_required
def view_courses():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    courses = cursor.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template('view_courses.html', courses=courses, user =current_user)
@app.route('/delete-course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Kiểm tra xem khóa học có được sử dụng trong lớp học không
        cursor.execute("SELECT COUNT(*) FROM classes WHERE course_id = ?", (course_id,))
        count = cursor.fetchone()[0]

        if count > 0:
            flash("Không thể xóa khóa học vì đang được sử dụng trong các lớp học!", "warning")
        else:
            cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            conn.commit()
            flash("Đã xóa khóa học thành công!", "success")

    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Lỗi khi xóa khóa học: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_courses'))

@app.route('/edit-course/<int:course_id>', methods=['POST', 'GET'])
@login_required 
def edit_course(course_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        cursor.execute('UPDATE courses SET name = ?, description = ? WHERE id = ?', (name, description, course_id))
        conn.commit()
        conn.close()
        flash("Đã cập nhật khóa học thành công!", "success")
        return redirect(url_for('view_courses'))
    else:
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
        course = cursor.fetchone()
        conn.close()
        if course:
            return render_template('admin/edit_course.html', course=course, user=current_user)
        else:
            flash("Khóa học không tồn tại!", "danger")
            return redirect(url_for('view_courses'))
    


# Thêm lớp học, xem danh sách lớp học
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
    return render_template('admin/add_class.html', courses=courses, teachers=teachers, rooms=rooms, user =current_user)

@app.route('/view-classes')
@login_required
def view_classes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    if( current_user.role == 'admin'): 
        query = """
            SELECT classes.id, courses.name, users.full_name, rooms.name, classes.capacity, classes.registered
            FROM classes
            JOIN courses ON classes.course_id = courses.id
            JOIN users ON classes.teacher_id = users.id
            JOIN rooms ON classes.room_id = rooms.id
        """
        classes = cursor.execute(query).fetchall()
    elif (current_user.role == 'teacher'):
        query = """
            SELECT classes.id, courses.name, users.full_name, rooms.name, classes.capacity, classes.registered
            FROM classes
            JOIN courses ON classes.course_id = courses.id
            JOIN users ON classes.teacher_id = users.id
            JOIN rooms ON classes.room_id = rooms.id
            where classes.teacher_id = ?
        """
        classes = cursor.execute(query, (current_user.id,)).fetchall()
    else:
        conn.close()
        return "Không có quyền truy cập", 403
    conn.close()
    return render_template('view_classes.html', classes=classes, user = current_user)

@app.route('/edit-class/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_class(class_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Lấy danh sách khóa học, giảng viên, và phòng
    courses = cursor.execute("SELECT id, name FROM courses").fetchall()
    teachers = cursor.execute("SELECT id, full_name FROM users WHERE role = 'teacher'").fetchall()
    rooms = cursor.execute("SELECT id, name FROM rooms").fetchall()

    # Lấy thông tin lớp cần sửa
    cursor.execute("SELECT course_id, teacher_id, room_id, capacity FROM classes WHERE id = ?", (class_id,))
    class_data = cursor.fetchone()

    if not class_data:
        conn.close()
        flash("Lớp học không tồn tại.", "danger")
        return redirect(url_for('view_classes'))

    if request.method == 'POST':
        new_course_id = request.form['course_id']
        new_teacher_id = request.form['teacher_id']
        new_room_id = request.form['room_id']
        new_capacity = request.form['capacity']

        try:
            cursor.execute("""
                UPDATE classes
                SET course_id = ?, teacher_id = ?, room_id = ?, capacity = ?
                WHERE id = ?
            """, (new_course_id, new_teacher_id, new_room_id, new_capacity, class_id))

            conn.commit()
            flash("Cập nhật lớp học thành công!", "success")
            return redirect(url_for('view_classes'))
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Lỗi khi cập nhật: {str(e)}", "danger")

    conn.close()
    return render_template('admin/edit_class.html', class_id=class_id,
                           class_data=class_data, courses=courses,
                           teachers=teachers, rooms=rooms, user=current_user)
@app.route('/delete-class/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Kiểm tra xem lớp đã có học viên đăng ký chưa
        cursor.execute("SELECT COUNT(*) FROM registrations WHERE class_id = ?", (class_id,))
        registration_count = cursor.fetchone()[0]

        if registration_count > 0:
            flash("Không thể xóa lớp học vì đã có học viên đăng ký.", "warning")
        else:
            cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            conn.commit()
            flash("Đã xóa lớp học thành công!", "success")
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Lỗi khi xóa lớp học: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_classes'))


# Xem danh sách người dùng
@app.route('/view-users')
@login_required
def view_users():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    users = cursor.execute("SELECT id, full_name, email, role FROM users").fetchall()
    conn.close()
    return render_template('admin/view_users.html', user=current_user, users=users)


# Đăng ký người dùng, chỉnh sửa role
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



# Thêm lịch học, giảng viên xem lịch dạy
@app.route('/add-schedule/<int:class_id>', methods=['GET', 'POST'])
@login_required
def add_schedule(class_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    if request.method == 'POST':
        day = request.form['day_of_week']
        start = request.form['start_time']
        end = request.form['end_time']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO schedules (class_id, day_of_week, start_time, end_time)
            VALUES (?, ?, ?, ?)
        """, (class_id, day, start, end))
        conn.commit()
        conn.close()

        flash("Đã thêm thời khóa biểu!", "success")
        return redirect(url_for('view_classes'))

    return render_template('admin/add_schedule.html', class_id=class_id)
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

    return render_template('teacher/teacher_schedule.html', schedule=result, user = current_user)


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



# Chạy app
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
