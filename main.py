import mysql.connector

conn = mysql.connector.connect(
    host="127.0.0.1",      # DB 서버 주소 (예: 127.0.0.1)
    user="root",        # MySQL 계정
    password="root",    # MySQL 계정 비밀번호
    database="projectdb"       # 사용할 데이터베이스
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM product")  # 예시 쿼리
rows = cursor.fetchall()
for row in rows:
    print(row)

cursor.close()
conn.close()

