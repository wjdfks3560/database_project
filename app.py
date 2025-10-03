from flask import Flask, render_template, request, jsonify
import mysql.connector
#from werkzeug.security import generate_password_hash

app = Flask(__name__)

# --- 데이터베이스 연결 설정 ---
db_config = {
    'host': 'localhost',
    'user': 'root',              # DB 사용자 이름
    'password': 'root',          # DB 비밀번호 (본인 설정에 맞게 수정)
    'database': 'projectdb'      # 사용할 데이터베이스 이름
}

# --- 라우팅 (경로 설정) ---

# 메인 페이지를 보여주는 경로
@app.route('/')
def main_page():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 상품 목록을 가져오는 SQL 쿼리
        sql = """
            SELECT 
                p.product_id, p.title, p.price, pi.image_url
            FROM 
                Product p
            LEFT JOIN 
                (SELECT product_id, MIN(image_id) as min_image_id FROM product_image GROUP BY product_id) p_first_image
                ON p.product_id = p_first_image.product_id
            LEFT JOIN 
                product_image pi ON pi.image_id = p_first_image.min_image_id
            -- WHERE p.status = '판매중'  <- 이 부분을 제거했습니다.
            ORDER BY 
                p.product_id DESC 
            LIMIT 10;
        """
        cursor.execute(sql)
        products = cursor.fetchall()

        for product in products:
            product['price'] = f"{product['price']:,}원"

    except mysql.connector.Error as err:
        print(f"데이터베이스 오류: {err}")
        products = []
    
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    
    return render_template('mainPage.html', products=products)

# 회원가입 페이지를 보여주는 경로
@app.route('/register_page')
def register_page():
    return render_template('register.html')

# 회원가입 데이터를 실제로 처리하는 경로
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('id')
    raw_password = data.get('password')
    name = data.get('name')
    email = data.get('email')
    tel = data.get('tel')
    
    #hashed_password = generate_password_hash(raw_password)

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        sql = "INSERT INTO User (id, password, user_name, email, phone_number) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (username, raw_password, name, email, tel))
        
        conn.commit()

        return jsonify({'status': 'success', 'message': '회원가입이 완료되었습니다.'})

    except mysql.connector.Error as err:
        return jsonify({'status': 'error', 'message': f'데이터베이스 오류: {err}'}), 500
    
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)