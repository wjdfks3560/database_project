from flask import Flask, render_template
import mysql.connector

# Flask 앱 생성
app = Flask(__name__)

# 데이터베이스 접속 정보 (본인 설정에 맞게 수정)
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '0826',
    'database': 'mydb'
}

# '/users' 경로에 접속하면 회원 목록을 보여주는 함수
@app.route('/users')
def user_list():
    conn = None
    cursor = None
    try:
        # 데이터베이스 연결
        conn = mysql.connector.connect(**db_config)
        # 커서 생성 (결과를 딕셔너리 형태로 받기 위해 dictionary=True 설정)
        cursor = conn.cursor(dictionary=True)
        
        # User 테이블의 모든 정보 조회
        cursor.execute("SELECT userid, user_name, id, email, join_date FROM User")
        
        # 조회된 모든 데이터 가져오기
        users = cursor.fetchall()
        
        # users.html 템플릿에 users 데이터를 담아 웹페이지로 보여주기
        return render_template('users.html', users=users)

    except Exception as e:
        return f"데이터베이스 연결 오류: {e}"
    
    finally:
        # 연결 및 커서 종료
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 이 파일이 직접 실행될 때 Flask 서버 구동
if __name__ == '__main__':
    app.run(debug=True)