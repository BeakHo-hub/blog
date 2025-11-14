from flask import Flask, render_template, request, g
import requests
import json
from urllib.parse import quote
import sqlite3
import os

# 1. Flask 애플리케이션을 한 번만 초기화합니다.
app = Flask(__name__)

# 데이터베이스 파일 이름 설정
DATABASE = 'search_rank.db'

# ★★★ 임시 조치: 실제 키 값을 코드 안에 직접 입력합니다. (깃허브 업로드 시 반드시 .env로 변경!) ★★★
NAVER_CLIENT_ID = "zQzxVxLPdlCs7JSDPAno"
NAVER_CLIENT_SECRET = "123123"

# --- 1. SQLite 연결 및 초기화 함수 ---

def get_db():
    """데이터베이스 연결 객체를 가져오거나 새로 생성합니다."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # 결과 행을 딕셔너리처럼 접근할 수 있도록 설정
        db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    """요청 처리가 끝날 때 데이터베이스 연결을 닫습니다."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """데이터베이스 테이블을 초기화합니다."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # search_count 테이블 생성: (id: 기본키, keyword: 검색어, count: 횟수)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_count (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                count INTEGER NOT NULL DEFAULT 1
            )
        """)
        db.commit()

# --- 2. 검색어 저장 및 횟수 업데이트 함수 ---

def increment_search_count(keyword):
    """검색어의 횟수를 1 증가시키거나, 새로운 검색어라면 추가합니다."""
    db = get_db()
    cursor = db.cursor()
    
    # 1. 이미 존재하는지 확인하고 횟수 업데이트
    cursor.execute(
        "UPDATE search_count SET count = count + 1 WHERE keyword = ?", 
        (keyword,)
    )
    
    # 2. 업데이트된 행이 없다면 (새로운 검색어라면) 삽입
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO search_count (keyword) VALUES (?)", 
            (keyword,)
        )
    
    db.commit()


# 네이버 블로그 검색 API 호출 함수
def search_naver_blog(query):
    # 검색어를 URL 인코딩합니다.
    enc_query = quote(query) 
    
    # 블로그 검색 API URL, 10개 결과, 정확도순 정렬
    url = f"https://openapi.naver.com/v1/search/blog.json?query={enc_query}&display=10&sort=sim"
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # 성공 시 검색 결과를 JSON에서 추출하여 반환
            return response.json().get('items', [])
        else:
            # API 호출 실패 시 명확한 오류 메시지 출력
            print("="*50)
            print(f"🚨 API 호출 실패! 상태 코드: {response.status_code}")
            if response.status_code == 401:
                print("키 오류 가능성: Client ID 또는 Secret을 확인하거나 서비스 환경 설정을 점검하세요.")
            print(f"응답 본문: {response.text}")
            print("="*50)
            return []
    except Exception as e:
        print(f"API 요청 중 오류 발생: {e}")
        return []

# 사용자가 요청한 "Hello World" 코드 (경로 /hello-world로 분리)
@app.route('/hello-world')
def hello_world_route():
    # 원했던 '이거는 뭐냐면 가상환경이에요' 메시지를 반환합니다.
    return 'Hello World! (이거는 뭐냐면 가상환경이에요)'


@app.route('/', methods=['GET'])
def index():
    # URL 쿼리 파라미터에서 'query' 값을 가져옵니다.
    search_query = request.args.get('query', '').strip() # 검색 전후 공백 제거
    
    results = []
    if search_query:
        # ★★★ 순위 저장 기능 추가: 검색어를 먼저 DB에 저장하고 횟수를 증가시킵니다.
        increment_search_count(search_query) 
        
        # 검색어가 있을 경우에만 API 호출
        results = search_naver_blog(search_query)

    # index.html 템플릿 렌더링
    return render_template('index.html', query=search_query, results=results)


@app.route('/ranking')
def ranking():
    """검색어 순위 페이지 라우트: DB에서 인기 검색어 10개를 가져와 보여줍니다."""
    db = get_db()
    cursor = db.cursor()
    
    # 횟수(count) 기준으로 내림차순 정렬하여 상위 10개 검색어를 가져옵니다.
    cursor.execute(
        "SELECT keyword, count FROM search_count ORDER BY count DESC LIMIT 10"
    )
    
    # 결과를 딕셔너리 리스트 형태로 가져옵니다.
    top_keywords = cursor.fetchall() 
    
    return render_template('ranking.html', top_keywords=top_keywords)


if __name__ == '__main__':
    # 2. 통합된 Flask 앱을 실행합니다.
    
    # ★★★ Flask 앱 실행 전에 데이터베이스 초기화 (테이블 생성)
    init_db() 
    
    # 실행 전: pip install flask requests sqlite3
    app.run(debug=True, host='0.0.0.0')