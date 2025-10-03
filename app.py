from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, abort
import mysql.connector
import os
from datetime import date
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- 파일 업로드 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 공통 DB 연결 설정/함수 ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'projectdb'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ======================================================================
#                           메인 페이지
# ======================================================================
@app.route('/')
def main_page():
    products = []
    conn = None
    cursor = None
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
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return render_template('main_page.html', products=products, session=session)

# ======================================================================
#                           회원가입
# ======================================================================
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

    conn = None
    cursor = None
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
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

# ======================================================================
#                           로그인 / 로그아웃
# ======================================================================
@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    username = data.get('id')
    password = data.get('password')
    conn = None
    cursor = None
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
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃 되었습니다.", "info")
    return redirect(url_for('main_page'))

# ======================================================================
#                         찜 (리스트) 기능
# ======================================================================
@app.route('/wishlist/add/<int:product_id>', methods=['POST'])
def wishlist_add(product_id):
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM wishlist WHERE userid=%s AND product_id=%s", (session['user_id'], product_id))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("INSERT INTO wishlist (userid, product_id) VALUES (%s, %s)", (session['user_id'], product_id))
            conn.commit()
            flash("찜 목록에 추가되었습니다!", "success")
        else:
            flash("이미 찜한 상품입니다.", "info")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/wishlist/remove/<int:product_id>', methods=['POST'])
def wishlist_remove(product_id):
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wishlist WHERE userid=%s AND product_id=%s", (session['user_id'], product_id))
        conn.commit()
        flash("찜 목록에서 삭제되었습니다.", "success")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return redirect(url_for('wishlist_page'))

@app.route('/wishlist')
def wishlist_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    products = []
    conn = None
    cursor = None
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
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return render_template('wishlist.html', products=products, session=session)

# ======================================================================
#                         상품 상세 / 댓글 / 찜 카운트
# ======================================================================
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = None
    images = []
    seller = None
    reviews = []
    comments = []
    is_wish = False
    current_user_id = session.get('user_id')

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 상세 정보
        cursor.execute("SELECT * FROM Product WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()
        if not product:
            abort(404)

        # 대표/추가 이미지
        cursor.execute("SELECT * FROM product_image WHERE product_id=%s ORDER BY image_id ASC", (product_id,))
        images = cursor.fetchall()

        # 판매자 이름
        cursor.execute("SELECT user_name FROM User WHERE userid=%s", (product['seller_id'],))
        seller = cursor.fetchone()

        # 구매후기 (Orders-Reviews)
        cursor.execute("""
            SELECT r.rating, r.comment, u.user_name AS buyer_name
            FROM Reviews r JOIN User u ON r.buyer_userid=u.userid
            WHERE r.orderid IN (SELECT orderid FROM Orders WHERE product_id=%s)
        """, (product_id,))
        reviews = cursor.fetchall()

        # 상세용 댓글 테이블(comment)도 함께 조회
        cursor.execute("""
            SELECT author, content, created_at
            FROM comment
            WHERE product_id=%s
            ORDER BY id DESC
            LIMIT 50
        """, (product_id,))
        comments = cursor.fetchall()

        # 조회수 +1
        cursor.execute("UPDATE Product SET view = COALESCE(view,0) + 1 WHERE product_id=%s", (product_id,))
        conn.commit()

        # 현재 사용자의 위시 여부
        if current_user_id:
            cursor.execute("SELECT 1 FROM wishlist WHERE userid=%s AND product_id=%s", (current_user_id, product_id))
            is_wish = cursor.fetchone() is not None
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return render_template(
        'product_detail.html',
        product=product,
        images=images,
        seller=seller,
        reviews=reviews,
        comments=comments,
        is_wish=is_wish,
        session=session
    )

@app.post("/product/<int:product_id>/comment")
def add_comment(product_id):
    author  = (request.form.get("author") or "익명").strip()
    content = (request.form.get("content") or "").strip()
    if not content:
        # 내용 없으면 상세로 복귀
        return redirect(url_for("product_detail", product_id=product_id) + "#comments")

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO comment(product_id, author, content) VALUES(%s,%s,%s)",
            (product_id, author, content)
        )
        conn.commit()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return redirect(url_for("product_detail", product_id=product_id) + "#comments")

@app.post("/product/<int:product_id>/wish")
def add_wish_counter(product_id):
    """개별 사용자 찜(wishlist)와 별개로 Product.wish_count 자체를 +1 하는 단순 카운터"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Product SET wish_count = COALESCE(wish_count,0)+1 WHERE product_id=%s", (product_id,))
        conn.commit()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return redirect(url_for("product_detail", product_id=product_id))

# ======================================================================
#                           상품 등록
# ======================================================================
def get_category_id_by_name(conn, name: str):
    cur = conn.cursor()
    try:
        cur.execute("SELECT category_id FROM Category WHERE name=%s", (name,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()

@app.route("/product/register", methods=["GET", "POST"])
def register_product():
    # GET: 등록 페이지 렌더(템플릿이 있다면)
    if request.method == "GET":
        return render_template("product_register.html")

    # POST: 등록 처리
    title       = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    price_raw   = request.form.get("price")
    category_nm = request.form.get("category")       # Category.name 기준
    file        = request.files.get("image")

    # 필수값 검증
    if not title or not description or not price_raw or not category_nm:
        flash("필수 항목이 누락되었습니다.", "warning")
        return redirect(url_for("register_product"))

    try:
        price = int(price_raw)
        if price < 0:
            flash("가격은 0 이상이어야 합니다.", "warning")
            return redirect(url_for("register_product"))
    except ValueError:
        flash("가격 형식이 올바르지 않습니다.", "warning")
        return redirect(url_for("register_product"))

    conn = get_db_connection()
    cur = None
    try:
        category_id = get_category_id_by_name(conn, category_nm)
        if category_id is None:
            flash(f"카테고리 [{category_nm}] 가 존재하지 않습니다. Category 테이블을 확인하세요.", "warning")
            return redirect(url_for("register_product"))

        # 로그인 연동 전이면 seller_id 임시 1, 로그인 시 세션 사용
        seller_id = session.get("user_id", 1)
        product_status = "판매중"

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Product
            (seller_id, category_id, title, description, price, view, wish_count, Product_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (seller_id, category_id, title, description, price, 0, 0, product_status))
        conn.commit()
        product_id = cur.lastrowid

        # 이미지 저장
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "jpg"
            fname = f"{uuid4().hex}.{ext}"
            save_path = os.path.join(UPLOAD_DIR, fname)
            file.save(save_path)
            image_url = f"/static/uploads/{fname}"

            cur.execute(
                "INSERT INTO product_image (product_id, image_url) VALUES (%s, %s)",
                (product_id, image_url)
            )
            conn.commit()

        flash("상품이 등록되었습니다.", "success")
        return redirect(url_for("product_detail", product_id=product_id))

    except mysql.connector.Error as err:
        print("DB Error:", err)
        flash("서버 오류가 발생했습니다.", "danger")
        return redirect(url_for("register_product"))
    finally:
        if cur is not None:
            cur.close()
        conn.close()

# ======================================================================
#                           내 주문 / 프로필 / 알림
# ======================================================================
@app.route('/orders')
def orders_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    orders = []
    conn = None
    cursor = None
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
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return render_template('orders.html', orders=orders, session=session)

@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = None
    profile = None
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE userid=%s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute("SELECT * FROM User_profile WHERE userid=%s", (session['user_id'],))
        profile = cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return render_template('profile.html', user=user, profile=profile, session=session)

@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    notifications = []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Notification WHERE seller_userid=%s", (session['user_id'],))
        notifications = cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    return render_template('notifications.html', notifications=notifications, session=session)

# ======================================================================
#                               앱 실행
# ======================================================================
if __name__ == '__main__':
    # host/port 변경 필요 시 아래 인자를 조정하세요.
    app.run(debug=True)
