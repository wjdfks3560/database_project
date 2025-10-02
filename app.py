from flask import Flask, render_template
import mysql.connector

# Flask 앱 생성
app = Flask(__name__)

def get_conn():
    return mysql.connector.connect(
        host="127.0.0.1",      # 또는 DB 서버 주소
        user="root",           # MySQL 사용자
        password="root",     # MySQL 비밀번호
        database="projectdb",  # 스키마명 (예: projectdb)
        charset="utf8mb4"
    )

# '/users' 경로에 접속하면 회원 목록을 보여주는 함수
@app.route("/users")
def users_list():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT userid, user_name, id, email, join_date FROM User;")
        users = cur.fetchall()   # [{ 'userid':1, 'user_name':'...', ... }, ...]
    finally:
        cur.close()
        conn.close()

    return render_template("users.html", users=users)

if __name__ == "__main__":
    app.run(debug=True)