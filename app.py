from flask import Flask, render_template, request, redirect, url_for, flash
from flask import Response, jsonify
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from datetime import datetime
from dateutil.parser import parse
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import emit
import os
from werkzeug.utils import secure_filename
import sqlite3
import json






app = Flask(__name__)
app.secret_key = 'secret123'
socketio = SocketIO(app)

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, full_name, email, role, image):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.role = role
        self.image = image

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, role, image FROM users WHERE id = ?", (user_id,))
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
        cursor.execute("SELECT id, full_name, email, role, image, password FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[5], password):
            login_user(User(user[0], user[1], user[2], user[3], user[4]))
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
        return render_template('student/index.html', user=current_user)
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


UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/add-course', methods=['GET', 'POST'])
@login_required
def add_course():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        image_file = request.files.get('image')
        image_filename = None

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(image_path)
            image_filename = filename

        try:
            conn = sqlite3.connect('database.db', timeout=10)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO courses (name, image, description)
                VALUES (?, ?, ?)
            """, (name, image_filename,  description))
            conn.commit()
            socketio.emit('course_added', {
                'name': name,            
                'image': image_filename,
                'description': description
            })
        except Exception as e:
            conn.rollback()
            flash(f"Lỗi khi thêm khóa học: {str(e)}", "danger")
        finally:
            conn.close()

        flash("✅ Đã thêm khóa học!", "success")
        
        return redirect(url_for('view_courses'))

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

    # Lấy dữ liệu để render form
    courses = cursor.execute("SELECT id, name FROM courses").fetchall()
    teachers = cursor.execute("SELECT id, full_name FROM users WHERE role = 'teacher'").fetchall()
    rooms = cursor.execute("SELECT id, name FROM rooms").fetchall()
    semesters = cursor.execute("SELECT id, name, start_date, end_date FROM semesters").fetchall()

    if request.method == 'POST':
        course_id = request.form['course_id']
        teacher_id = request.form['teacher_id']
        room_id = request.form['room_id']
        capacity = request.form['capacity']
        semester_id = request.form['semester_id']

        try:
            # Thêm lớp mới
            cursor.execute("""
                INSERT INTO classes (course_id, teacher_id, room_id, capacity, semester_id)
                VALUES (?, ?, ?, ?, ?)
            """, (course_id, teacher_id, room_id, capacity, semester_id))
            conn.commit()

            # Lấy ID lớp vừa thêm
            cursor.execute("SELECT last_insert_rowid()")
            new_class_id = cursor.fetchone()[0]

            # Truy vấn lại chi tiết lớp học
            cursor.execute("""
                SELECT cl.id, co.name, u.full_name, r.name, cl.capacity, cl.registered, s.name, cl.teacher_id
                FROM classes cl
                JOIN courses co ON cl.course_id = co.id
                JOIN users u ON cl.teacher_id = u.id
                JOIN rooms r ON cl.room_id = r.id
                JOIN semesters s ON cl.semester_id = s.id
                WHERE cl.id = ?
            """, (new_class_id,))
            new_class = cursor.fetchone()

            # Gửi realtime đến tất cả (JS phía client sẽ lọc teacher_id phù hợp)
            socketio.emit('class_added', {
                'id': new_class[0],
                'course': new_class[1],
                'teacher': new_class[2],
                'room': new_class[3],
                'capacity': new_class[4],
                'registered': new_class[5],
                'semester': new_class[6],
                'teacher_id': new_class[7]
            })

            flash("✅ Đã tạo lớp học thành công!", "success")
            return redirect(url_for('view_classes'))

        except Exception as e:
            conn.rollback()
            flash(f"❌ Lỗi khi tạo lớp học: {str(e)}", "danger")

    conn.close()
    return render_template(
        'admin/add_class.html',
        user=current_user,
        courses=courses,
        teachers=teachers,
        rooms=rooms,
        semesters=semesters
    )


@app.route('/view-classes')
@login_required
def view_classes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if current_user.role == 'admin':
        query = """
            SELECT 
                classes.id, courses.name, users.full_name, rooms.name, 
                classes.capacity, classes.registered, semesters.name
            FROM classes
            JOIN courses ON classes.course_id = courses.id
            JOIN users ON classes.teacher_id = users.id
            JOIN rooms ON classes.room_id = rooms.id
            JOIN semesters ON classes.semester_id = semesters.id
        """
        classes = cursor.execute(query).fetchall()

    elif current_user.role == 'teacher':
        query = """
            SELECT 
                classes.id, courses.name, users.full_name, rooms.name, 
                classes.capacity, classes.registered, semesters.name
            FROM classes
            JOIN courses ON classes.course_id = courses.id
            JOIN users ON classes.teacher_id = users.id
            JOIN rooms ON classes.room_id = rooms.id
            JOIN semesters ON classes.semester_id = semesters.id
            WHERE classes.teacher_id = ?
        """
        classes = cursor.execute(query, (current_user.id,)).fetchall()
    else:
        conn.close()
        return "Không có quyền truy cập", 403

    conn.close()
    return render_template('view_classes.html', classes=classes, user=current_user)


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

@app.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Kiểm tra xem người dùng có đang đăng ký lớp nào không
        cursor.execute("SELECT COUNT(*) FROM registrations WHERE id = ?", (user_id,))
        registration_count = cursor.fetchone()[0]

        if registration_count > 0:
            flash("Không thể xóa người dùng vì đã có lớp học đăng ký.", "warning")
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash("Đã xóa người dùng thành công!", "success")
    except sqlite3.Error as e:
        conn.rollback()
        flash(f"Lỗi khi xóa người dùng: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('view_users'))
# Đăng ký người dùng, chỉnh sửa role
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if role == 'teacher':
            flash("Không thể đăng ký vai trò giảng viên, liên hệ Admin để được phân quyền.", "danger")
            return redirect(url_for('register'))

        dob = request.form.get('dob')
        phone = request.form.get('phone')
        gender = request.form.get('gender')
        cccd = request.form.get('cccd')

        image_file = request.files.get('image')
        if not image_file or not allowed_file(image_file.filename):
            flash("Vui lòng chọn ảnh đại diện hợp lệ (jpg, png, jpeg, gif)", "danger")
            return redirect(url_for('register'))

        image_filename = secure_filename(image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        image_file.save(image_path)

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (full_name, email, password, role, dob, phone, gender, cccd, image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (full_name, email, hashed_password, role, dob, phone, gender, cccd, image_filename))
            conn.commit()
            # Sau khi commit đăng ký xong:
            socketio.emit('user_registered', {
                'full_name': full_name,
                'email': email,
                'role': role
            })
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

    new_role = request.form.get('role')
    admin_password = request.form.get('admin_password')

    if not admin_password:
        flash("❌ Vui lòng nhập mật khẩu để xác nhận!", "danger")
        return redirect(url_for('view_users'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE id = ?", (current_user.id,))
    stored_hash = cursor.fetchone()[0]

    if not check_password_hash(stored_hash, admin_password):
        flash("❌ Mật khẩu không đúng!", "danger")
        conn.close()
        return redirect(url_for('view_users'))

    try:
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, id))
        conn.commit()
        socketio.emit('role_updated', {'user_id': id, 'new_role': new_role})
        flash("✅ Cập nhật vai trò thành công!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Lỗi khi cập nhật vai trò: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('view_users'))


# Chuyển hướng khi thay đổi role k reload

from threading import Timer

def delayed_emit(user_id, new_role):
    socketio.emit('role_updated', {'user_id': user_id, 'new_role': new_role})
@app.route('/teacher')
@login_required
def teacher_dashboard():
    return render_template('teacher/teacher.html', user=current_user)
@app.route('/student')
@login_required
def student_dashboard():
    return render_template('student/index.html', user=current_user)
# Thêm lịch học, giảng viên xem lịch dạy
@app.route('/add-schedule', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Lấy danh sách lớp để cho chọn khi tạo thời khóa biểu
    classes = cursor.execute("""
        SELECT classes.id, courses.name, users.full_name 
        FROM classes
        JOIN courses ON classes.course_id = courses.id
        JOIN users ON classes.teacher_id = users.id
    """).fetchall()

    if request.method == 'POST':
        class_id = request.form['class_id']
        day = request.form['day_of_week']
        start = request.form['start_time']
        end = request.form['end_time']

        cursor.execute("""
            INSERT INTO schedules (class_id, day_of_week, start_time, end_time)
            VALUES (?, ?, ?, ?)
        """, (class_id, day, start, end))
        conn.commit()
        conn.close()
        flash("Đã thêm thời khóa biểu!", "success")
        return redirect(url_for('view_classes'))

    conn.close()
    return render_template('admin/add_schedule.html', classes=classes, user=current_user)

@app.route('/teacher-schedule')
@login_required
def teacher_schedule():
    if current_user.role != 'teacher':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
        SELECT c.id, co.name, s.date, s.day_of_week, s.start_time, s.end_time, r.name
        FROM classes c
        JOIN courses co ON c.course_id = co.id
        JOIN schedules s ON s.class_id = c.id
        JOIN rooms r ON c.room_id = r.id
        WHERE c.teacher_id = ?
        ORDER BY s.date, s.start_time
    """
    result = cursor.execute(query, (current_user.id,)).fetchall()
    conn.close()

    return render_template('teacher/teacher_schedule.html', schedule=result, user=current_user)


@app.route('/teacher-calendar')
@login_required
def teacher_calendar():
    if current_user.role != 'teacher':
        return "Không có quyền truy cập", 403
    return render_template('teacher/teacher_calendar.html', user=current_user)


@app.route('/api/teacher-schedules')
@login_required
def api_teacher_schedules():
    if current_user.role != 'teacher':
        return jsonify([])

    start_raw = request.args.get('start', '')
    end_raw = request.args.get('end', '')

    try:
        start_date = parse(start_raw).date()
        end_date = parse(end_raw).date()
    except Exception as e:
        return jsonify([])

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
        SELECT s.date, s.start_time, s.end_time, r.name, co.name
        FROM schedules s
        JOIN classes c ON s.class_id = c.id
        JOIN rooms r ON c.room_id = r.id
        JOIN courses co ON c.course_id = co.id
        WHERE c.teacher_id = ? AND s.date BETWEEN ? AND ?
    """
    data = cursor.execute(query, (current_user.id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).fetchall()
    conn.close()

    events = []
    for row in data:
        date, start, end, room, course = row
        events.append({
            'title': f"{start} - {end} - {room}: {course}",
            'start': f"{date}T{start}:00",
            'end': f"{date}T{end}:00"
        })

    return jsonify(events)

# Xem danh sách student đã đăng ký lớp học của mình
@app.route('/teacher/my-class')
@login_required
def teacher_my_class():
    if current_user.role != 'teacher':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Lấy tất cả lớp mà giảng viên hiện tại phụ trách
    query = """
        SELECT c.id AS class_id, co.name AS course_name, r.name AS room_name, c.capacity, c.registered
        FROM classes c
        JOIN courses co ON c.course_id = co.id
        JOIN rooms r ON c.room_id = r.id
        WHERE c.teacher_id = ?
    """
    classes = cursor.execute(query, (current_user.id,)).fetchall()

    # Lấy danh sách sinh viên đã đăng ký theo từng lớp
    registrations = {}
    for cls in classes:
        class_id = cls[0]
        cursor.execute("""
            SELECT u.full_name, u.email
            FROM registrations reg
            JOIN users u ON reg.student_id = u.id
            WHERE reg.class_id = ?
        """, (class_id,))
        registrations[class_id] = cursor.fetchall()

    conn.close()

    return render_template('teacher/my_class.html', classes=classes, registrations=registrations, user=current_user)

# Lấy lớp để gán lịch, thêm lịch thời khóa biểu
@app.route('/api/classes')
def get_classes():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT classes.id, rooms.name, courses.name
        FROM classes
        JOIN rooms ON classes.room_id = rooms.id
        JOIN courses ON classes.course_id = courses.id
    """)

    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        class_id, room_name, course_name = row
        result.append({
            "id": class_id,
            "label": f"Phòng {room_name}: {course_name}"
        })

    return Response(
        json.dumps(result, ensure_ascii=False),
        mimetype='application/json'
    )

# @app.route('/api/schedules', methods=['POST'])
# def save_schedule():
#     data = request.get_json()
#     class_ids = data.get('class_ids', [])
#     day_of_week = data.get('day_of_week')
#     start_time = data.get('start_time')
#     end_time = data.get('end_time')

#     if not class_ids or not day_of_week or not start_time or not end_time:
#         return jsonify({'success': False, 'message': 'Thiếu thông tin lịch'}), 400

#     conn = sqlite3.connect('database.db')
#     cursor = conn.cursor()

#     try:
#         # 🔍 Lấy danh sách (teacher_id, course_name) từ các class_ids
#         teacher_ids = []
#         for class_id in class_ids:
#             cursor.execute("""
#                 SELECT teacher_id FROM classes WHERE id = ?
#             """, (class_id,))
#             teacher = cursor.fetchone()
#             if teacher:
#                 teacher_ids.append((class_id, teacher[0]))

#         # ✅ Kiểm tra trùng lịch của giảng viên
#         for class_id, teacher_id in teacher_ids:
#             cursor.execute("""
#                 SELECT s.id FROM schedules s
#                 JOIN classes c ON s.class_id = c.id
#                 WHERE c.teacher_id = ?
#                 AND s.day_of_week = ?
#                 AND (
#                     (? < s.end_time AND ? > s.start_time)
#                 )
#             """, (teacher_id, day_of_week, start_time, end_time))

#             conflict = cursor.fetchone()
#             if conflict:
#                 return jsonify({
#                     'success': False,
#                     'message': f"Giảng viên đã có lớp khác vào khoảng {start_time} - {end_time} ngày {day_of_week}."
#                 }), 400

#         # Nếu không có xung đột, tiến hành lưu từng lớp
#         for class_id in class_ids:
#             cursor.execute("""
#                 INSERT INTO schedules (class_id, day_of_week, start_time, end_time)
#                 VALUES (?, ?, ?, ?)
#             """, (class_id, day_of_week, start_time, end_time))

#         conn.commit()
#         return jsonify({'success': True})

#     except Exception as e:
#         conn.rollback()
#         return jsonify({'success': False, 'message': str(e)}), 500

#     finally:
#         conn.close()
@app.route('/api/schedules', methods=['POST'])
def save_schedule():
    data = request.get_json()
    class_ids = data.get('class_ids', [])
    day_of_week = data.get('day_of_week')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    selected_date = data.get('date')  # dạng yyyy-MM-dd

    if not class_ids or not day_of_week or not start_time or not end_time or not selected_date:
        return jsonify({'success': False, 'message': 'Thiếu thông tin lịch'}), 400

    try:
        selected_date_obj = datetime.datetime.strptime(selected_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Định dạng ngày không hợp lệ'}), 400

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        for class_id in class_ids:
            # Lấy học kỳ và thông tin lớp
            cursor.execute("""
                SELECT c.teacher_id, c.room_id, s.start_date, s.end_date
                FROM classes c
                JOIN semesters s ON c.semester_id = s.id
                WHERE c.id = ?
            """, (class_id,))
            result = cursor.fetchone()

            if not result:
                return jsonify({'success': False, 'message': 'Lớp chưa được gán học kỳ hoặc không tồn tại'}), 400

            teacher_id, room_id, semester_start, semester_end = result
            semester_start = datetime.datetime.strptime(semester_start, "%Y-%m-%d").date()
            semester_end = datetime.datetime.strptime(semester_end, "%Y-%m-%d").date()

            weekday_target = selected_date_obj.weekday()  # 0=Thứ 2

            # Lặp qua các ngày trong học kỳ
            current_date = semester_start
            delta = datetime.timedelta(days=1)

            while current_date <= semester_end:
                if current_date.weekday() == weekday_target:
                    date_str = current_date.strftime("%Y-%m-%d")

                    # 1. Kiểm tra trùng lịch với lớp hiện tại
                    cursor.execute("""
                        SELECT id FROM schedules
                        WHERE class_id = ? AND date = ?
                        AND ( (? < end_time AND ? > start_time) )
                    """, (class_id, date_str, start_time, end_time))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': f"Lớp đã có lịch vào {date_str}"}), 400

                    # 2. Kiểm tra trùng lịch với giáo viên
                    cursor.execute("""
                        SELECT s.id FROM schedules s
                        JOIN classes c ON s.class_id = c.id
                        WHERE c.teacher_id = ?
                        AND s.date = ?
                        AND ( (? < s.end_time AND ? > s.start_time) )
                    """, (teacher_id, date_str, start_time, end_time))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': f"Giảng viên đã có lịch vào {date_str}"}), 400

                    # 3. Kiểm tra trùng lịch với phòng học
                    cursor.execute("""
                        SELECT s.id FROM schedules s
                        JOIN classes c ON s.class_id = c.id
                        WHERE c.room_id = ?
                        AND s.date = ?
                        AND ( (? < s.end_time AND ? > s.start_time) )
                    """, (room_id, date_str, start_time, end_time))
                    if cursor.fetchone():
                        return jsonify({'success': False, 'message': f"Phòng học đã được sử dụng vào {date_str}"}), 400

                    # ✅ Nếu không có xung đột thì lưu
                    cursor.execute("""
                        INSERT INTO schedules (class_id, day_of_week, start_time, end_time, date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (class_id, day_of_week, start_time, end_time, date_str))

                current_date += delta

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()




# @app.route('/api/schedules')
# def load_schedules():
#     def get_date_for_weekday(day_of_week):
#         mapping = {
#             'Mon': '2025-07-28',
#             'Tue': '2025-07-29',
#             'Wed': '2025-07-30',
#             'Thu': '2025-07-31',
#             'Fri': '2025-08-01',
#             'Sat': '2025-08-02',
#             'Sun': '2025-08-03',
#         }
#         return mapping.get(day_of_week, '2025-07-28')  # fallback là thứ 2

#     conn = sqlite3.connect('database.db')
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT s.day_of_week, s.start_time, s.end_time, r.name, c.name
#         FROM schedules s
#         JOIN classes cl ON s.class_id = cl.id
#         JOIN rooms r ON cl.room_id = r.id
#         JOIN courses c ON cl.course_id = c.id
#     """)

#     rows = cursor.fetchall()
#     conn.close()

#     events = []
#     for day_of_week, start, end, room, course in rows:
#         date_str = get_date_for_weekday(day_of_week)
#         start_iso = f"{date_str}T{start}:00"
#         end_iso = f"{date_str}T{end}:00"

#         events.append({
#             'title': f"{room}: {course}",
#             'start': start_iso,
#             'end': end_iso,
#             'extendedProps': {
#                 'room': room,
#                 'course': course,
#                 'start_time': start,
#                 'end_time': end
#             }
#         })

#     return jsonify(events)

import datetime

@app.route('/api/schedules')
def load_schedules():
    start_raw = request.args.get('start', '')
    try:
        start_date = parse(start_raw).date()
    except Exception as e:
        print("❌ Lỗi parse ngày:", e)
        return jsonify([])

    end_raw = request.args.get('end', '')
    try:
        end_date = parse(end_raw).date()
    except:
        end_date = start_date + datetime.timedelta(days=6)

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.date, s.start_time, s.end_time, r.name, c.name
        FROM schedules s
        JOIN classes cl ON s.class_id = cl.id
        JOIN rooms r ON cl.room_id = r.id
        JOIN courses c ON cl.course_id = c.id
        WHERE s.date BETWEEN ? AND ?
    """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))

    rows = cursor.fetchall()
    conn.close()

    events = []
    for date_str, start, end, room, course in rows:
        events.append({
            'title': f"{room}: {course}",
            'start': f"{date_str}T{start}:00",
            'end': f"{date_str}T{end}:00",
            'extendedProps': {
                'room': room,
                'course': course,
                'start_time': start,
                'end_time': end
            }
        })

    return jsonify(events)



# Tạo học kỳ
@app.route('/add-semester', methods=['GET', 'POST'])
@login_required
def add_semester():
    if current_user.role != 'admin':
        return "Không có quyền truy cập", 403

    if request.method == 'POST':
        name = request.form['name']
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO semesters (name, start_date, end_date)
            VALUES (?, ?, ?)
        """, (name, start_date, end_date))
        conn.commit()
        conn.close()
        flash("✅ Đã thêm học kỳ mới!", "success")
        return redirect(url_for('add_semester'))

    return render_template('admin/add_semester.html', user=current_user)


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

@app.route('/init-semester')
def init_semester():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,  -- yyyy-MM-dd
            end_date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    return "✅ Đã tạo bảng semesters nếu chưa có."
@app.route('/alter-classes-add-semester')
def alter_classes_add_semester():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
            ALTER TABLE classes ADD COLUMN semester_id INTEGER REFERENCES semesters(id)
        """)
        conn.commit()
        return "✅ Đã thêm cột semester_id vào bảng classes."
    except Exception as e:
        return f"⚠️ Có thể cột đã tồn tại: {str(e)}"
    finally:
        conn.close()

@app.route('/init-schedule-date')
def init_schedule_date_column():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Kiểm tra xem cột 'date' đã tồn tại chưa
        cursor.execute("PRAGMA table_info(schedules)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'date' not in columns:
            cursor.execute("ALTER TABLE schedules ADD COLUMN date TEXT")
            conn.commit()
            message = "✅ Đã thêm cột 'date' vào bảng schedules."
        else:
            message = "ℹ️ Cột 'date' đã tồn tại trong bảng schedules."

        conn.close()
        return message
    except Exception as e:
        return f"❌ Lỗi khi thêm cột 'date': {str(e)}"


@app.route('/')
def index():
    return render_template('index.html')



# Student

@app.route('/courses')
def student_courses_static():
    return render_template('student/courses.html')

# Hiển thị lớp
@app.route('/student/courses')
@login_required
def student_courses():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
        SELECT cl.id, co.name, u.full_name, r.name, cl.capacity, cl.registered, co.image, u.image, s.name
        FROM classes cl
        JOIN courses co ON cl.course_id = co.id
        JOIN users u ON cl.teacher_id = u.id
        JOIN rooms r ON cl.room_id = r.id
        JOIN semesters s ON cl.semester_id = s.id
    """
    classes = cursor.execute(query).fetchall()

    cursor.execute("SELECT class_id FROM registrations WHERE student_id = ?", (current_user.id,))
    registered_class_ids = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template('student/courses.html', user=current_user, classes=classes, registered_class_ids=registered_class_ids)

@app.route('/register-class', methods=['POST'])
@login_required
def register_class():
    if current_user.role != 'student':
        return jsonify({"success": False, "message": "Chỉ học viên được phép đăng ký"}), 403

    class_id = request.form.get('class_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # 1. Lấy capacity và sĩ số hiện tại
    cursor.execute("SELECT capacity, registered FROM classes WHERE id = ?", (class_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({"success": False, "message": "Không tìm thấy lớp học"})
    capacity, registered = result
    if registered >= capacity:
        conn.close()
        return jsonify({"success": False, "message": "Lớp đã đầy, không thể đăng ký!"})

    # 2. Lấy lịch học lớp này
    cursor.execute("SELECT date, start_time, end_time FROM schedules WHERE class_id = ?", (class_id,))
    new_schedule = cursor.fetchall()

    # 3. Lấy danh sách class_id đã đăng ký của học viên
    cursor.execute("SELECT class_id FROM registrations WHERE student_id = ?", (current_user.id,))
    registered_ids = [row[0] for row in cursor.fetchall()]

    student_schedule = []
    if registered_ids:
        placeholders = ','.join('?' for _ in registered_ids)
        cursor.execute(f"""
            SELECT date, start_time, end_time FROM schedules
            WHERE class_id IN ({placeholders})
        """, registered_ids)
        student_schedule = cursor.fetchall()

    # 4. Check trùng lịch
    for new_date, new_start, new_end in new_schedule:
        for ex_date, ex_start, ex_end in student_schedule:
            if new_date == ex_date and not (new_end <= ex_start or new_start >= ex_end):
                conn.close()
                return jsonify({"success": False, "message": "❌ Trùng lịch học với lớp đã đăng ký!"})

    try:
        # 5. Thêm đăng ký mới
        cursor.execute("INSERT INTO registrations (class_id, student_id, register_time) VALUES (?, ?, ?)",
                       (class_id, current_user.id, datetime.datetime.now()))
        cursor.execute("UPDATE classes SET registered = registered + 1 WHERE id = ?", (class_id,))
        conn.commit()

        # Truy vấn lại sĩ số và capacity
        cursor.execute("SELECT registered, capacity FROM classes WHERE id = ?", (class_id,))
        reg, cap = cursor.fetchone()

        socketio.emit('class_registered', {
            'class_id': int(class_id),
            'new_registered': reg,
            'is_full': reg >= cap
        })

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()


@app.route('/unregister-class', methods=['POST'])
@login_required
def unregister_class():
    if current_user.role != 'student':
        return jsonify({"success": False, "message": "Chỉ học viên mới được phép huỷ đăng ký!"}), 403

    class_id = request.form.get('class_id')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM registrations WHERE student_id = ? AND class_id = ?", (current_user.id, class_id))
        cursor.execute("UPDATE classes SET registered = registered - 1 WHERE id = ? AND registered > 0", (class_id,))
        conn.commit()

        cursor.execute("SELECT registered, capacity FROM classes WHERE id = ?", (class_id,))
        reg, cap = cursor.fetchone()

        socketio.emit('class_registered', {
            'class_id': int(class_id),
            'new_registered': reg,
            'is_full': reg >= cap
        })

        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()



@app.route('/class-schedule/<int:class_id>')
@login_required
def get_schedule(class_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT day_of_week FROM schedules WHERE class_id = ?", (class_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row[0] for row in rows])

@app.route('/student/my-classes')
@login_required
def student_my_classes():
    if current_user.role != 'student':
        return "Không có quyền truy cập", 403

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = """
        SELECT cl.id, co.name, u.full_name, r.name, cl.capacity, cl.registered, co.image, s.name
        FROM registrations reg
        JOIN classes cl ON reg.class_id = cl.id
        JOIN courses co ON cl.course_id = co.id
        JOIN users u ON cl.teacher_id = u.id
        JOIN rooms r ON cl.room_id = r.id
        JOIN semesters s ON cl.semester_id = s.id
        WHERE reg.student_id = ?
    """
    cursor.execute(query, (current_user.id,))
    classes = cursor.fetchall()
    conn.close()

    return render_template('student/my_classes.html', user=current_user, classes=classes)

@app.route('/student/schedule')
@login_required
def student_schedule():
    if current_user.role != 'student':
        return "Không có quyền truy cập", 403
    return render_template('student/student_schedule.html', user=current_user)

@app.route('/student')
def index_student():
    return render_template('student/index.html')

@app.route('/student/schedule/<int:class_id>')
@login_required
def view_schedule_by_class(class_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT day_of_week, date, start_time, end_time
        FROM schedules
        WHERE class_id = ?
        ORDER BY date
    """, (class_id,))
    schedule = cursor.fetchall()
    conn.close()

    return render_template('student/schedule.html', user=current_user, schedule=schedule)
@app.route('/api/student-schedules')
@login_required
def student_schedule_api():
    if current_user.role != 'student':
        return jsonify([])

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Lấy thông tin lịch học của tất cả các lớp mà học sinh đã đăng ký
    query = """
        SELECT co.name, r.name, s.date, s.start_time, s.end_time
        FROM registrations reg
        JOIN classes cl ON reg.class_id = cl.id
        JOIN courses co ON cl.course_id = co.id
        JOIN rooms r ON cl.room_id = r.id
        JOIN schedules s ON s.class_id = cl.id
        WHERE reg.student_id = ?
    """
    cursor.execute(query, (current_user.id,))
    rows = cursor.fetchall()
    conn.close()

    # Format theo yêu cầu FullCalendar
    events = []
    for course_name, room_name, date, start_time, end_time in rows:
        events.append({
            "title": f"{course_name} - {room_name}",
            "start": f"{date}T{start_time}",
            "end": f"{date}T{end_time}"
        })

    return jsonify(events)



@app.route('/init-images')
def init_images_column():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Thêm cột image vào bảng users nếu chưa có
        cursor.execute("ALTER TABLE users ADD COLUMN image TEXT")

    except sqlite3.OperationalError as e:
        print("❗ users.image đã tồn tại:", e)

    try:
        # Thêm cột image vào bảng courses nếu chưa có
        cursor.execute("ALTER TABLE courses ADD COLUMN image TEXT")
    except sqlite3.OperationalError as e:
        print("❗ courses.image đã tồn tại:", e)

    conn.commit()
    conn.close()
    return "✅ Đã thêm cột 'image' cho bảng users và courses (nếu chưa có)."



# Chạy app
if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
