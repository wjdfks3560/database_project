from flask import Flask, render_template, request, session, redirect, url_for, flash
import mysql.connector
import os
from datetime import date

app = Flask(__name__)
app.secret_key = os.urandom(24)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'projectdb'
}

# --- 공통 DB 연결 함수 ---
def get_db_connection():
    return mysql.connector.connect(**db_config)

# --- 메인 페이지 ---
@app.route('/')
def main_page():
    products = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT p.product_id, p.title, CAST(p.price AS UNSIGNED) AS price, pi.image_url
            FROM Product p
            LEFT JOIN (
                SELECT product_id, MIN(image_id) AS min_image_id
                FROM product_image
                GROUP BY product_id
            ) AS first_image ON p.product_id = first_image.product_id
            LEFT JOIN product_image pi ON pi.image_id = first_image.min_image_id
            ORDER BY COALESCE(p.view,0) DESC, p.product_id DESC
            LIMIT 8
        """
        cursor.execute(sql)
        products = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template('main_page.html', products=products, session=session)

# --- 회원가입 ---
@app.route('/register_page')
def register_page():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    username = data.get('id')
    password = data.get('password')
    name = data.get('name')
    email = data.get('email')
    phone = data.get('tel')
    address = data.get('address')

    if not all([username, password, name, email, phone, address]):
        return render_template('register.html', error="모든 필드를 입력해주세요.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = date.today().strftime('%Y-%m-%d')
        sql = """
            INSERT INTO User (id, password, user_name, email, phone_number, address, join_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (username, password, name, email, phone, address, today))
        conn.commit()
        flash("회원가입이 완료되었습니다. 로그인 해주세요.", "success")
        return redirect(url_for('login_page'))
    except mysql.connector.Error as err:
        return render_template('register.html', error=f"DB 오류: {err}")
    finally:
        cursor.close()
        conn.close()

# --- 로그인 / 로그아웃 ---
@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    username = data.get('id')
    password = data.get('password')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT userid, password FROM User WHERE id=%s", (username,))
        user = cursor.fetchone()
        if user and user['password'] == password:
            session['user_id'] = user['userid']
            session['username'] = username
            flash("로그인 성공!", "success")
            return redirect(url_for('main_page'))
        else:
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "warning")
            return redirect(url_for('login_page'))
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for('main_page'))

# --- 찜 추가/삭제 ---
@app.route('/wishlist/add/<int:product_id>', methods=['POST'])
def wishlist_add(product_id):
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wishlist WHERE userid=%s AND product_id=%s", (session['user_id'], product_id))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("INSERT INTO wishlist (userid, product_id) VALUES (%s, %s)", (session['user_id'], product_id))
            conn.commit()
            flash("찜 목록에 추가되었습니다!", "success")
        else:
            flash("이미 찜한 상품입니다.", "info")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/wishlist/remove/<int:product_id>', methods=['POST'])
def wishlist_remove(product_id):
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wishlist WHERE userid=%s AND product_id=%s", (session['user_id'], product_id))
        conn.commit()
        flash("찜 목록에서 삭제되었습니다.", "success")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('wishlist_page'))

# --- 찜 페이지 ---
@app.route('/wishlist')
def wishlist_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    products = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT p.product_id, p.title, CAST(p.price AS UNSIGNED) AS price, pi.image_url
            FROM Product p
            JOIN wishlist w ON p.product_id = w.product_id
            LEFT JOIN (
                SELECT product_id, MIN(image_id) AS min_image_id
                FROM product_image
                GROUP BY product_id
            ) AS first_image ON p.product_id = first_image.product_id
            LEFT JOIN product_image pi ON pi.image_id = first_image.min_image_id
            WHERE w.userid=%s
        """
        cursor.execute(sql, (session['user_id'],))
        products = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template('wishlist.html', products=products, session=session)

# --- 상품 상세 페이지 ---
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = None
    images = []
    seller = None
    reviews = []
    is_wish = False
    current_user_id = session.get('user_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Product WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()

        cursor.execute("SELECT * FROM product_image WHERE product_id=%s", (product_id,))
        images = cursor.fetchall()

        cursor.execute("SELECT user_name FROM User WHERE userid=%s", (product['seller_id'],))
        seller = cursor.fetchone()

        cursor.execute("""
            SELECT r.rating, r.comment, u.user_name AS buyer_name
            FROM Reviews r JOIN User u ON r.buyer_userid=u.userid
            WHERE r.orderid IN (SELECT orderid FROM Orders WHERE product_id=%s)
        """, (product_id,))
        reviews = cursor.fetchall()

        if current_user_id:
            cursor.execute("SELECT * FROM wishlist WHERE userid=%s AND product_id=%s", (current_user_id, product_id))
            is_wish = cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()
    return render_template('product_detail.html', product=product, images=images, seller=seller, reviews=reviews, is_wish=is_wish, session=session)

# --- 내 주문 페이지 ---
@app.route('/orders')
def orders_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    orders = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT o.orderid, p.title, o.order_status, pay.sale_price, pay.method
            FROM Orders o
            JOIN Product p ON o.product_id = p.product_id
            LEFT JOIN Payment pay ON o.orderid = pay.orderid
            WHERE o.buyer_userid=%s
        """
        cursor.execute(sql, (session['user_id'],))
        orders = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template('orders.html', orders=orders, session=session)

# --- 내 프로필 페이지 ---
@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = None
    profile = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE userid=%s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute("SELECT * FROM User_profile WHERE userid=%s", (session['user_id'],))
        profile = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    return render_template('profile.html', user=user, profile=profile, session=session)

# --- 알림 페이지 ---
@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    notifications = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Notification WHERE seller_userid=%s", (session['user_id'],))
        notifications = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template('notifications.html', notifications=notifications, session=session)


if __name__ == '__main__':
    app.run(debug=True)
