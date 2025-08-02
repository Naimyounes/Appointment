# الكود الكامل المطلوب لإضافة API إلى الموقع المستضاف
# يجب إضافة هذا الكود إلى ملف app.py على https://appointment-1-96c4.onrender.com/

"""
ملف app.py الكامل للموقع المستضاف
يجب استبدال المحتوى الحالي بهذا الكود الكامل
"""

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# إعدادات منفصلة عن ClinicEase لتجنب تداخل الـ sessions
app.secret_key = 'web_api_appointments_secret_key_2024_unique_render'

# إعدادات Cookie منفصلة لتجنب التداخل مع ClinicEase
app.config['SESSION_COOKIE_NAME'] = 'appointments_api_session'
app.config['SESSION_COOKIE_SECURE'] = True  # للإنتاج على HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 دقيقة

# إعدادات قاعدة البيانات
DATABASE = 'appointments.db'
API_TOKEN = '123456'  # نفس الـ token المستخدم في ClinicEase

def init_db():
    """إنشاء قاعدة البيانات والجدول"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            note TEXT,
            status TEXT DEFAULT 'قيد التأكيد',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """الحصول على اتصال بقاعدة البيانات"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def is_time_slot_available(date, time, appointment_id=None):
    """التحقق من توفر الموعد"""
    conn = get_db_connection()
    
    if appointment_id:
        # استثناء الموعد الحالي عند التحديث
        query = "SELECT COUNT(*) FROM appointments WHERE date = ? AND time = ? AND id != ?"
        result = conn.execute(query, (date, time, appointment_id)).fetchone()
    else:
        query = "SELECT COUNT(*) FROM appointments WHERE date = ? AND time = ?"
        result = conn.execute(query, (date, time)).fetchone()
    
    conn.close()
    return result[0] == 0

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/book', methods=['GET', 'POST'])
def book():
    """صفحة الحجز"""
    if request.method == 'POST':
        # استلام البيانات من النموذج
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        date = request.form.get('date', '').strip()
        time = request.form.get('time', '').strip()
        note = request.form.get('note', '').strip()
        
        # التحقق من البيانات المطلوبة
        if not all([name, phone, date, time]):
            flash('جميع الحقول مطلوبة باستثناء سبب الزيارة', 'error')
            return render_template('book.html')
        
        # التحقق من صحة رقم الهاتف الجزائري
        import re
        phone_pattern = r'^0[567]\d{8}$'
        if not re.match(phone_pattern, phone.replace(' ', '')):
            flash('يرجى إدخال رقم هاتف جزائري صحيح (مثال: 0551234567)', 'error')
            return render_template('book.html')
        
        # التحقق من صحة التاريخ والوقت
        try:
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()
            
            # دمج التاريخ والوقت
            appointment_datetime = datetime.combine(appointment_date, appointment_time)
            current_datetime = datetime.now()
            
            # إضافة هامش زمني 30 دقيقة للحجز المسبق
            from datetime import timedelta
            minimum_booking_time = current_datetime + timedelta(minutes=30)
            
            # التحقق من أن الموعد ليس في الماضي أو قريب جداً
            if appointment_datetime <= minimum_booking_time:
                flash('يجب حجز الموعد قبل 30 دقيقة على الأقل من الوقت الحالي', 'error')
                return render_template('book.html')
                
        except ValueError:
            flash('تاريخ أو وقت غير صحيح', 'error')
            return render_template('book.html')
        
        # التحقق من توفر الموعد
        if not is_time_slot_available(date, time):
            flash('هذا الموعد محجوز مسبقاً، يرجى اختيار وقت آخر', 'error')
            return render_template('book.html')
        
        # حفظ الموعد في قاعدة البيانات
        try:
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO appointments (name, phone, date, time, note, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, phone, date, time, note, 'قيد التأكيد'))
            conn.commit()
            conn.close()
            
            flash('تم حجز الموعد بنجاح! سيتم التواصل معك قريباً لتأكيد الموعد.', 'success')
            return redirect(url_for('book'))
            
        except Exception as e:
            flash('حدث خطأ أثناء حفظ الموعد، يرجى المحاولة مرة أخرى', 'error')
            return render_template('book.html')
    
    return render_template('book.html')

# ===== API ENDPOINTS المطلوبة لـ ClinicEase =====

@app.route('/api/appointments/all')
def api_all_appointments():
    """API endpoint لاسترجاع جميع المواعيد"""
    # التحقق من الـ token
    token = request.args.get('token')
    if token != API_TOKEN:
        return jsonify({'error': 'Unauthorized - Invalid token'}), 401
    
    # معاملات اختيارية للفلترة
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    
    try:
        conn = get_db_connection()
        
        # بناء الاستعلام حسب المعاملات
        query = '''
            SELECT id, name, phone, date, time, note, status, created_at
            FROM appointments 
        '''
        params = []
        conditions = []
        
        if status_filter:
            conditions.append('status = ?')
            params.append(status_filter)
        
        if date_filter:
            conditions.append('date = ?')
            params.append(date_filter)
        
        if conditions:
            query += 'WHERE ' + ' AND '.join(conditions) + ' '
        
        query += 'ORDER BY date ASC, time ASC'
        
        appointments = conn.execute(query, params).fetchall()
        conn.close()
        
        # تحويل النتائج إلى قائمة من القواميس
        appointments_list = []
        for appointment in appointments:
            appointments_list.append({
                'id': appointment['id'],
                'name': appointment['name'],
                'phone': appointment['phone'],
                'date': appointment['date'],
                'time': appointment['time'],
                'note': appointment['note'],
                'status': appointment['status'],
                'created_at': appointment['created_at']
            })
        
        return jsonify({
            'appointments': appointments_list,
            'count': len(appointments_list),
            'filters': {
                'status': status_filter,
                'date': date_filter
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/appointments/<int:appointment_id>/status', methods=['PUT'])
def update_appointment_status(appointment_id):
    """API endpoint لتعديل حالة الموعد"""
    # التحقق من الـ token
    token = request.args.get('token')
    if token != API_TOKEN:
        return jsonify({'error': 'Unauthorized - Invalid token'}), 401
    
    # التحقق من وجود البيانات المطلوبة
    if not request.json or 'status' not in request.json:
        return jsonify({'error': 'Missing status field in request body'}), 400
    
    new_status = request.json['status'].strip()
    
    # التحقق من صحة الحالة الجديدة
    valid_statuses = ['قيد التأكيد', 'مؤكد', 'ملغي', 'مكتمل']
    if new_status not in valid_statuses:
        return jsonify({
            'error': 'Invalid status',
            'valid_statuses': valid_statuses
        }), 400
    
    try:
        conn = get_db_connection()
        
        # التحقق من وجود الموعد
        appointment = conn.execute(
            'SELECT id, name, status FROM appointments WHERE id = ?',
            (appointment_id,)
        ).fetchone()
        
        if not appointment:
            conn.close()
            return jsonify({'error': 'Appointment not found'}), 404
        
        # تحديث حالة الموعد
        conn.execute(
            'UPDATE appointments SET status = ? WHERE id = ?',
            (new_status, appointment_id)
        )
        conn.commit()
        
        # استرجاع البيانات المحدثة
        updated_appointment = conn.execute('''
            SELECT id, name, phone, date, time, note, status, created_at
            FROM appointments WHERE id = ?
        ''', (appointment_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            'message': 'Status updated successfully',
            'appointment': {
                'id': updated_appointment['id'],
                'name': updated_appointment['name'],
                'phone': updated_appointment['phone'],
                'date': updated_appointment['date'],
                'time': updated_appointment['time'],
                'note': updated_appointment['note'],
                'status': updated_appointment['status'],
                'created_at': updated_appointment['created_at']
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# ===== API ENDPOINTS إضافية =====

@app.route('/api/appointments', methods=['GET'])
def api_appointments():
    """API endpoint لاسترجاع المواعيد غير المؤكدة (للتوافق)"""
    # التحقق من الـ token
    token = request.args.get('token')
    if token != API_TOKEN:
        return jsonify({'error': 'Unauthorized - Invalid token'}), 401
    
    try:
        conn = get_db_connection()
        appointments = conn.execute('''
            SELECT id, name, phone, date, time, note, status, created_at
            FROM appointments 
            WHERE status = 'قيد التأكيد'
            ORDER BY date ASC, time ASC
        ''').fetchall()
        conn.close()
        
        # تحويل النتائج إلى قائمة من القواميس
        appointments_list = []
        for appointment in appointments:
            appointments_list.append({
                'id': appointment['id'],
                'name': appointment['name'],
                'phone': appointment['phone'],
                'date': appointment['date'],
                'time': appointment['time'],
                'note': appointment['note'],
                'status': appointment['status'],
                'created_at': appointment['created_at']
            })
        
        return jsonify({
            'appointments': appointments_list,
            'count': len(appointments_list)
        })
        
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500

# ===== صفحات إضافية =====

@app.route('/appointments')
def view_appointments():
    """صفحة عرض جميع المواعيد"""
    return render_template('appointments.html')

@app.route('/appointments/admin')
def admin_appointments():
    """صفحة إدارة المواعيد للمدير"""
    return render_template('admin_appointments.html')

if __name__ == '__main__':
    # إنشاء قاعدة البيانات عند بدء التشغيل
    init_db()
    
    # تشغيل التطبيق
    app.run(debug=True, host='0.0.0.0', port=4000)

"""
===== تعليمات التطبيق =====

1. اذهب لـ https://render.com/
2. افتح مشروع appointment-1-96c4
3. استبدل محتوى ملف app.py بالكود أعلاه
4. احفظ التغييرات
5. انتظر إعادة النشر التلقائي

===== النتيجة المتوقعة =====

بعد النشر، ستعمل هذه الـ URLs:

✅ https://appointment-1-96c4.onrender.com/ - الصفحة الرئيسية
✅ https://appointment-1-96c4.onrender.com/book - صفحة الحجز
✅ https://appointment-1-96c4.onrender.com/api/appointments/all?token=123456 - API
✅ https://appointment-1-96c4.onrender.com/api/appointments/1/status?token=123456 - تحديث حالة

===== اختبار API =====

بعد النشر، اختبر:

PowerShell:
Invoke-WebRequest -Uri "https://appointment-1-96c4.onrender.com/api/appointments/all?token=123456"

يجب أن يرجع: 200 OK مع بيانات JSON

===== ميزات الكود =====

✅ Session منفصل عن ClinicEase
✅ API كامل للمواعيد الأونلاين
✅ أمان بـ token
✅ معالجة أخطاء شاملة
✅ توافق مع HTTPS على Render
✅ قاعدة بيانات SQLite
✅ فلترة المواعيد حسب الحالة والتاريخ
"""
