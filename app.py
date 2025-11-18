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
    'password': '0826',
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
            
            WHERE p.Product_status = '판매중' 
            
            
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
#                                 도움말
# ======================================================================

# [추가] 분석 보고서 페이지를 위한 라우트
@app.route('/report')
def report_page():
    return render_template('report.html')

# ======================================================================
#                                 검색 기능
# ======================================================================
@app.route('/search')
def search():
    # 1. 사용자가 입력한 검색어를 URL에서 가져옵니다 (예: /search?q=노트북)
    query = request.args.get('q', '').strip()

    # 검색어가 없으면 메인 페이지로 돌려보냅니다.
    if not query:
        return redirect(url_for('main_page'))

    products = []
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 2. 검색어 타입에 따라 다른 SQL 쿼리를 준비합니다.
        # '@'로 시작하면 사용자 ID 또는 이름으로 검색
        if query.startswith('@'):
            search_term = f"%{query[1:]}%"
            sql = """
                SELECT p.product_id, p.title, CAST(p.price AS UNSIGNED) AS price, 
                       (SELECT pi.image_url FROM product_image pi WHERE pi.product_id = p.product_id ORDER BY pi.image_id LIMIT 1) as image_url
                FROM Product p
                JOIN User u ON p.seller_id = u.userid
                WHERE u.id LIKE %s OR u.user_name LIKE %s
                
                AND p.Product_status = '판매중' 
                
                ORDER BY p.product_id DESC
            """
            cursor.execute(sql, (search_term, search_term))
        # 그 외의 경우, 상품 제목 또는 판매자 주소로 검색
        else:
            search_term = f"%{query}%"
            sql = """
                SELECT p.product_id, p.title, CAST(p.price AS UNSIGNED) AS price, 
                       (SELECT pi.image_url FROM product_image pi WHERE pi.product_id = p.product_id ORDER BY pi.image_id LIMIT 1) as image_url
                FROM Product p
                JOIN User u ON p.seller_id = u.userid
                JOIN Category c ON p.category_id = c.category_id
                WHERE p.title LIKE %s OR u.address LIKE %s OR c.name LIKE %s
                ORDER BY p.product_id DESC
            """
            cursor.execute(sql, (search_term, search_term, search_term))
        
        products = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    # 3. search_results.html 템플릿에 검색 결과와 검색어를 전달하여 페이지를 보여줍니다.
    return render_template('search_results.html', products=products, query=query)


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
            # 상품 카운트 +1
            cursor.execute("""
                UPDATE Product
                SET wish_count = COALESCE(wish_count,0) + 1
                WHERE product_id=%s
            """, (product_id,))
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
        deleted = cursor.rowcount

# 삭제가 실제로 일어났다면 wish_count -1 (0 미만 방지)
        if deleted:
            cursor.execute("""
                UPDATE Product
                SET wish_count = GREATEST(COALESCE(wish_count,0)-1, 0)
                WHERE product_id=%s
            """, (product_id,))

        conn.commit()
        flash("찜 목록에서 삭제되었습니다.", "success")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return redirect(url_for('product_detail', product_id=product_id))

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
            ORDER BY p.product_id DESC
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

    is_seller = False
    
    # 목록에서 들어온 표시 + 세션 중복 방지용
    src = request.args.get('src') # list면 목록에서 클릭
    viewed = set(session.get('viewed_once', []))  # 이번 브라우저 세션에서 이미 센 상품id들

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

        # product['category_id']를 이용해 Category 테이블에서 이름(name)을 찾습니다.
        cursor.execute("SELECT name FROM Category WHERE category_id = %s", (product['category_id'],))
        category_row = cursor.fetchone()
        
        # 찾은 이름을 product 정보 안에 'category_name'이라는 이름으로 넣어줍니다.
        if category_row:
            product['category_name'] = category_row['name']
        else:
            product['category_name'] = "미분류"

        # product 정보를 가져온 후, 현재 유저와 판매자 ID 비교
        if product and current_user_id == product['seller_id']:
            is_seller = True    

        # 대표/추가 이미지
        cursor.execute("SELECT * FROM product_image WHERE product_id=%s ORDER BY image_id ASC", (product_id,))
        images = cursor.fetchall()

        # 판매자 정보(아이디 + 이름 둘 다 가져오기)
        cursor.execute(
            "SELECT userid, user_name FROM User WHERE userid=%s",
            (product['seller_id'],)
        )
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

        # ★ 조회수 증가: '목록에서 클릭해 들어온 최초 1회'만
        if src == 'list' and product_id not in viewed:
            cursor.execute(
                "UPDATE Product SET view = COALESCE(view,0) + 1 WHERE product_id=%s",
                (product_id,)
            )
        conn.commit()
        viewed.add(product_id)
        session['viewed_once'] = list(viewed)

        # 현재 사용자의 위시 여부
        if current_user_id:
            cursor.execute(
                "SELECT 1 FROM wishlist WHERE userid=%s AND product_id=%s",
                (current_user_id, product_id)
            )
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
        is_seller=is_seller,
        session=session
    )

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
#                             주문/결제 페이지
# ======================================================================
@app.route('/payment/<int:product_id>', methods=['GET', 'POST'])
def payment_page(product_id):
    # 1. 로그인 필수: 로그인하지 않은 사용자는 로그인 페이지로 보냅니다.
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 2. 상품 정보 조회: URL로 받은 product_id를 사용해 DB에서 상품 정보를 가져옵니다.
        cursor.execute("SELECT * FROM Product WHERE product_id=%s", (product_id,))
        product = cursor.fetchone()

        # 3. 본인 상품 구매 방지 확인
        # 상품의 판매자 ID와 현재 로그인한 ID가 같은지 확인합니다.
        if product['seller_id'] == session['user_id']:
            flash("본인이 등록한 상품은 구매할 수 없습니다.", "warning")
            # 상품 상세 페이지로 돌려보냅니다.
            return redirect(url_for('product_detail', product_id=product_id))

        if not product:
            flash("존재하지 않는 상품입니다.", "danger")
            return redirect(url_for('main_page'))
        

        # 추가: 상품이 '판매중' 상태인지 확인 (GET/POST 공통 차단 로직)
        if product.get('Product_status') != '판매중':
            flash("이미 거래가 완료되었거나 판매 중이 아닌 상품입니다.", "danger")
            # 상세 페이지로 돌려보내 상태를 확인하게 하는 것이 더 좋습니다.
            return redirect(url_for('product_detail', product_id=product_id))



          # '결제하기' 버튼을 눌렀을 때의 처리를 추가 (POST)
        if request.method == 'POST':
            # Orders 테이블에 주문 추가
            status = '거래완료'
            seller_id = product['seller_id']
            sql_order = "INSERT INTO Orders (buyer_userid, seller_userid, product_id, order_status) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_order, (session['user_id'], seller_id, product_id, status))
            #cursor.execute("SELECT LAST_INSERT_ID()")
            #new_order_id = cursor.fetchone()['LAST_INSERT_ID()']


            new_order_id = cursor.lastrowid  # 새로 추가된 주문의 ID 가져오기

            # Payment 테이블에 결제 정보 추가
            payment_method = request.form.get('payment_method', 'card')
            method_text = '카드' if payment_method == 'card' else '계좌이체'
            sale_price = int(product['price'])
            paymentcol_value = 'N/A' # NOT NULL 제약조건 대비

            # paymentid를 사용하지 않고 orderid, sale_price, method, paymentcol만 사용
            sql_payment = "INSERT INTO Payment (orderid, sale_price, method, paymentcol) VALUES (%s, %s, %s, %s)"


             # 1. paymentid를 수동으로 찾아오기 (새로 추가된 부분)
            cursor.execute("SELECT MAX(paymentid) AS max_id FROM Payment")
            max_id_result = cursor.fetchone()
            # 만약 테이블이 비어있으면 1부터 시작, 아니면 가장 큰 값에 1을 더함
            next_payment_id = (max_id_result['max_id'] or 0) + 1
            
            payment_method = request.form.get('payment_method', 'card')
            method_text = '카드' if payment_method == 'card' else '계좌이체'
            sale_price = int(product['price'])
            paymentcol_value = 'N/A'

            # 2. paymentcol에 임시 값 넣어주기 (수정된 부분)
            #paymentcol_value = '' # 임시로 빈 값을 넣어줍니다.
            

            # 변수 4개 (orderid, sale_price, method_text, paymentcol_value)만 전달
            #cursor.execute(sql_payment, (new_order_id, sale_price, method_text, paymentcol_value))
            
            
            
            #conn.commit() # 모든 DB 변경사항을 최종 저장
            #flash("결제가 완료되었습니다.", "success")
            #return redirect(url_for('orders_page'))


            #cursor.execute(sql_payment, (new_order_id, sale_price, method_text, paymentcol_value))
            # 추가/수정: 상품 상태를 '거래완료'로 업데이트
            #sql_update_product = "UPDATE Product SET Product_status = '거래완료' WHERE product_id = %s"
            sql_payment = "INSERT INTO Payment (paymentid, orderid, sale_price, method, paymentcol) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql_payment, (next_payment_id, new_order_id, sale_price, method_text, paymentcol_value))
           
            # 3. Product 테이블 상태 업데이트
            sql_update_product = "UPDATE Product SET Product_status = '거래완료' WHERE product_id = %s"
            cursor.execute(sql_update_product, (product_id,))


            conn.commit() # 모든 DB 변경사항을 최종 저장
            flash("결제가 완료되었습니다.", "success")
            return redirect(url_for('orders_page')) # 주문 내역 페이지로 이동

        

        # 3. 사용자 정보 조회: 세션에 저장된 user_id로 현재 로그인한 사용자의 정보를 가져옵니다.
        cursor.execute("SELECT * FROM User WHERE userid=%s", (session['user_id'],))
        user = cursor.fetchone()

        # 4. payment.html 렌더링: 조회한 상품과 사용자 정보를 템플릿으로 넘겨줍니다.
        return render_template('payment.html', product=product, user=user)
   
    except mysql.connector.Error as err:
        print(f"DB Error: {err}")

        if conn is not None:
            conn.rollback() # 오류 발생 시 롤백

        flash("결제 페이지를 여는 중 오류가 발생했습니다.", "danger")
        return redirect(url_for('main_page'))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ======================================================================
#                               리뷰 작성
# ======================================================================
@app.route('/review/<int:order_id>', methods=['POST'])
def review_page(order_id):
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for('login_page'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1) 이 주문이 나의 주문인지 + 판매자 ID 가져오기
        cursor.execute("""
            SELECT o.orderid,
                   o.product_id,
                   o.order_status,
                   o.seller_userid
              FROM Orders o
             WHERE o.orderid = %s
               AND o.buyer_userid = %s
        """, (order_id, session['user_id']))
        order = cursor.fetchone()
        if not order:
            abort(404)

        # 2) 이미 리뷰를 작성했는지 먼저 확인
        cursor.execute("""
            SELECT 1
              FROM Reviews
             WHERE orderid = %s
               AND buyer_userid = %s
             LIMIT 1
        """, (order_id, session['user_id']))
        if cursor.fetchone():
            flash("이미 이 주문에 대한 후기를 작성하셨습니다.", "info")
            return redirect(url_for('orders_page'))

        # 3) 평점/코멘트 읽기
        rating_raw = request.form.get('rating', '')
        comment = (request.form.get('comment') or '').strip()

        try:
            rating = int(rating_raw)
        except ValueError:
            rating = 0
        if rating < 1 or rating > 5:
            flash("평점은 1~5 사이에서 선택해 주세요.", "warning")
            return redirect(url_for('orders_page'))

        # 4) 새 리뷰 INSERT (중복 없음 보장)
        cursor.execute("""
            INSERT INTO Reviews (orderid, buyer_userid, seller_userid, rating, comment)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id,
              session['user_id'],
              order['seller_userid'],
              rating,
              comment))
        conn.commit()

        flash("후기가 저장되었습니다.", "success")
        return redirect(url_for('orders_page'))

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


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
    # --- 로그인 체크 ---
    if 'user_id' not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("login_page"))
    
    # GET: 등록 페이지 렌더(템플릿이 있다면)
    if request.method == "GET":
        return render_template("register_product.html")

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
            SELECT o.orderid,
                   p.title,
                   o.order_status,
                   pay.sale_price,
                   pay.method,
                   (SELECT pi.image_url
                      FROM product_image pi
                     WHERE pi.product_id = p.product_id
                     ORDER BY pi.image_id
                     LIMIT 1) AS image_url,
                   CASE WHEN r.orderid IS NULL THEN 0 ELSE 1 END AS has_review
              FROM Orders o
              JOIN Product p ON o.product_id = p.product_id
         LEFT JOIN Payment pay ON o.orderid = pay.orderid
         LEFT JOIN Reviews r
                ON r.orderid = o.orderid
               AND r.buyer_userid = o.buyer_userid
             WHERE o.buyer_userid = %s
             ORDER BY o.orderid DESC
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
    selling_products = []
    seller_reviews = []
    avg_rating = None
    review_count = 0

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 내 기본 정보
        cursor.execute("SELECT * FROM User WHERE userid=%s", (session['user_id'],))
        user = cursor.fetchone()

        # 프로필(자기소개 등)
        cursor.execute("SELECT * FROM User_profile WHERE userid=%s", (session['user_id'],))
        profile = cursor.fetchone()

        # 내가 판매중인 상품
        cursor.execute("""
            SELECT p.product_id,
                   p.title,
                   CAST(p.price AS UNSIGNED) AS price,
                   (SELECT pi.image_url
                      FROM product_image pi
                     WHERE pi.product_id = p.product_id
                     ORDER BY pi.image_id
                     LIMIT 1) AS image_url
              FROM Product p
             WHERE p.seller_id = %s
               AND p.Product_status = '판매중'
             ORDER BY p.product_id DESC
             LIMIT 40
        """, (session['user_id'],))
        selling_products = cursor.fetchall()

        # (1) 내가 판매자로 받은 리뷰들의 평균 평점 & 개수
        cursor.execute("""
            SELECT AVG(r.rating) AS avg_rating,
                   COUNT(*)       AS review_cnt
              FROM Reviews r
             WHERE r.seller_userid = %s
        """, (session['user_id'],))
        row = cursor.fetchone()
        if row:
            avg_rating = row['avg_rating']
            review_count = row['review_cnt'] or 0

        # (2) 내가 판매한 상품에 달린 리뷰 목록
        cursor.execute("""
            SELECT r.rating,
                   r.comment,
                   u.user_name AS buyer_name,
                   p.title     AS product_title
              FROM Reviews r
              JOIN Orders  o ON r.orderid     = o.orderid
              JOIN Product p ON o.product_id  = p.product_id
              JOIN User    u ON r.buyer_userid = u.userid
             WHERE r.seller_userid = %s
             ORDER BY r.orderid DESC
             LIMIT 50
        """, (session['user_id'],))
        seller_reviews = cursor.fetchall()

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return render_template(
        'profile.html',
        user=user,
        profile=profile,
        selling_products=selling_products,
        avg_rating=avg_rating,
        review_count=review_count,
        seller_reviews=seller_reviews,
        session=session
    )

@app.route('/profile/bio/update', methods=['POST'])
def update_bio():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    bio_text = (request.form.get('bio') or '').strip()

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 먼저 UPDATE 시도
        cursor.execute(
            "UPDATE User_profile SET bio=%s WHERE userid=%s",
            (bio_text, session['user_id'])
        )

        # 해당 row가 없으면 INSERT
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO User_profile (userid, bio) VALUES (%s, %s)",
                (session['user_id'], bio_text)
            )

        conn.commit()
        flash("자기소개가 저장되었습니다.", "success")
    except mysql.connector.Error as err:
        print("DB Error:", err)
        flash("자기소개 저장 중 오류가 발생했습니다.", "danger")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    return redirect(url_for('profile_page'))

# ======================================================================
#                         판매자 상점(프로필) 페이지
# ======================================================================
@app.route('/shop/<int:user_id>')
def shop_profile(user_id):
    """특정 판매자(user_id)의 상점 페이지 (누구나 보기 가능)"""

    user = None
    profile = None
    selling_products = []
    seller_reviews = []
    avg_rating = None
    review_count = 0

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1) 판매자 기본 정보
        cursor.execute("SELECT * FROM User WHERE userid=%s", (user_id,))
        user = cursor.fetchone()
        if not user:
            # 존재하지 않는 사용자면 404
            abort(404)

        # 2) 상점 프로필(자기소개)
        cursor.execute("SELECT * FROM User_profile WHERE userid=%s", (user_id,))
        profile = cursor.fetchone()

        # 3) 이 판매자가 판매중인 상품
        cursor.execute("""
            SELECT p.product_id,
                   p.title,
                   CAST(p.price AS UNSIGNED) AS price,
                   (SELECT pi.image_url
                      FROM product_image pi
                     WHERE pi.product_id = p.product_id
                     ORDER BY pi.image_id
                     LIMIT 1) AS image_url
              FROM Product p
             WHERE p.seller_id = %s
               AND p.Product_status = '판매중'
             ORDER BY p.product_id DESC
             LIMIT 40
        """, (user_id,))
        selling_products = cursor.fetchall()

        # 4) 이 판매자(seller_userid = user_id)가 받은 리뷰들의 평균 평점/개수
        cursor.execute("""
            SELECT AVG(r.rating) AS avg_rating,
                   COUNT(*)       AS review_cnt
              FROM Reviews r
             WHERE r.seller_userid = %s
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            avg_rating = row['avg_rating']
            review_count = row['review_cnt'] or 0

        # 5) 이 판매자가 받은 리뷰 목록
        cursor.execute("""
            SELECT r.rating,
                   r.comment,
                   u.user_name AS buyer_name,
                   p.title     AS product_title
              FROM Reviews r
              JOIN Orders  o ON r.orderid     = o.orderid
              JOIN Product p ON o.product_id  = p.product_id
              JOIN User    u ON r.buyer_userid = u.userid
             WHERE r.seller_userid = %s
             ORDER BY r.orderid DESC
             LIMIT 50
        """, (user_id,))
        seller_reviews = cursor.fetchall()

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    # profile.html 을 그대로 재사용
    return render_template(
        'profile.html',
        user=user,
        profile=profile,
        selling_products=selling_products,
        avg_rating=avg_rating,
        review_count=review_count,
        seller_reviews=seller_reviews,
        session=session
    )


# ======================================================================
#                               앱 실행
# ======================================================================
if __name__ == '__main__':
    # host/port 변경 필요 시 아래 인자를 조정하세요.
    app.run(debug=True)