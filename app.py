from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # يجب تغييرها في الإنتاج

# إعدادات قاعدة البيانات
DATABASE = 'appointments.db'
API_TOKEN = '123456'  # يجب تغييرها في الإنتاج

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

@app.route('/api/appointments')
def api_appointments():
    """API endpoint لاسترجاع المواعيد غير المؤكدة"""
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

if __name__ == '__main__':
    # إنشاء قاعدة البيانات عند بدء التشغيل
    init_db()
    
    # تشغيل التطبيق
    app.run(debug=True, host='0.0.0.0', port=4000)