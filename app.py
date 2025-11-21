from flask import Flask, render_template, request, g, redirect, url_for
import requests
import json
from urllib.parse import quote
import sqlite3
import os
from bs4 import BeautifulSoup 

# 1. Flask 애플리케이션을 한 번만 초기화합니다.
app = Flask(__name__)

# 데이터베이스 파일 이름 설정
DATABASE = 'search_rank.db'

# ★★★ 임시 조치: 실제 키 값을 코드 안에 직접 입력합니다. ★★★
NAVER_CLIENT_ID = "zQzxVxLPdlCs7JSDPAno"
NAVER_CLIENT_SECRET = "Vg5F4UAH4J"

# --- 1. SQLite 연결 및 초기화 함수 ---

def get_db():
    """데이터베이스 연결 객체를 가져오거나 새로 생성합니다."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    """요청 처리가 끝날 때 데이터베이스 연결을 닫습니다."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """데이터베이스 테이블을 초기화합니다. (멜론 테이블 추가)"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 1. 검색어 횟수 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_count (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL,
                count INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        # 2. 멜론 차트 데이터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS melon_chart_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ranking INTEGER NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                UNIQUE(ranking)
            )
        """)
        db.commit()

# --- 2. 검색어 저장 및 횟수 업데이트 함수 ---

def increment_search_count(keyword):
    """검색어의 횟수를 1 증가시키거나, 새로운 검색어라면 추가합니다."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE search_count SET count = count + 1 WHERE keyword = ?", 
        (keyword,)
    )
    if cursor.rowcount == 0:
        cursor.execute(
            "INSERT INTO search_count (keyword) VALUES (?)", 
            (keyword,)
        )
    db.commit()

# --- 3. 네이버 블로그 검색 API 호출 함수 ---

def search_naver_blog(query):
    enc_query = quote(query) 
    url = f"https://openapi.naver.com/v1/search/blog.json?query={enc_query}&display=10&sort=sim"
    
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
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

# --- 4. 멜론 차트 크롤링 및 DB 저장 함수 ---

def fetch_melon_chart():
    """멜론 웹사이트에서 차트 데이터를 크롤링하여 가져옵니다."""
    url = "https://www.melon.com/chart/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"멜론 차트 접속 실패: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        chart_data = []
        list_items = soup.select('.lst50, .lst100')
        
        for item in list_items:
            rank = item.select_one('.rank').text.strip()
            title_element = item.select_one('.ellipsis.rank01 a')
            title = title_element.text.strip() if title_element else "제목 없음"
            artist_element = item.select_one('.ellipsis.rank02 a')
            artist = artist_element.text.strip() if artist_element else "아티스트 없음"
            
            if rank.isdigit():
                chart_data.append({
                    'rank': int(rank),
                    'title': title,
                    'artist': artist
                })
            
        return chart_data
        
    except Exception as e:
        print(f"멜론 차트 크롤링 중 오류 발생: {e}")
        return []

def save_melon_chart_to_db(chart_data):
    """크롤링된 데이터를 DB에 저장하고 기존 데이터를 삭제합니다."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("DELETE FROM melon_chart_data")
    
    for item in chart_data:
        try:
            cursor.execute(
                "INSERT INTO melon_chart_data (ranking, title, artist) VALUES (?, ?, ?)",
                (item['rank'], item['title'], item['artist'])
            )
        except sqlite3.IntegrityError:
            pass
            
    db.commit()

# --- 5. 라우트 함수 및 신규 순위 로직 ---

def get_artist_count_ranking():
    """DB에 저장된 멜론 차트 데이터를 기반으로 가수별 곡 수를 계산합니다."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT 
            artist, 
            COUNT(title) as song_count
        FROM melon_chart_data
        GROUP BY artist
        ORDER BY song_count DESC, artist ASC
        LIMIT 10
    """)
    
    return cursor.fetchall()


@app.route('/hello-world')
def hello_world_route():
    return 'Hello World! (이거는 뭐냐면 가상환경이에요)'

@app.route('/')
def main_menu():
    """메인 메뉴 페이지 (새로운 시작 페이지)"""
    return render_template('main_menu.html')

@app.route('/blog', methods=['GET'])
def blog_search():
    """맛집 검색 페이지"""
    search_query = request.args.get('query', '').strip()
    results = []
    if search_query:
        increment_search_count(search_query) 
        results = search_naver_blog(search_query)
    
    return render_template('search.html', query=search_query, results=results)


@app.route('/ranking')
def ranking():
    """검색어 순위 페이지 라우트"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT keyword, count FROM search_count ORDER BY count DESC LIMIT 10"
    )
    top_keywords = cursor.fetchall() 
    return render_template('ranking.html', top_keywords=top_keywords)


@app.route('/artist-ranking') # 새로 추가된 라우트
def artist_ranking():
    """가수별 차트 진입 곡 수 순위를 표시하는 라우트"""
    top_artists = get_artist_count_ranking()
    return render_template('artist_ranking.html', top_artists=top_artists)


@app.route('/melon-chart') 
def melon_chart():
    """멜론 차트 데이터를 DB에서 가져와 표시하는 라우트"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT ranking, title, artist FROM melon_chart_data ORDER BY ranking ASC"
    )
    chart_list = cursor.fetchall()
    
    return render_template('melon_chart.html', chart_list=chart_list)

@app.route('/update-chart-db') 
def update_chart_db():
    """멜론 차트를 크롤링하고 DB에 저장하는 기능을 실행합니다."""
    chart_data = fetch_melon_chart()
    if chart_data:
        save_melon_chart_to_db(chart_data)
    return redirect(url_for('melon_chart'))


@app.route('/artist-search', methods=['GET'])
def artist_search():
    """가수 검색창 페이지를 보여주거나 검색 결과를 처리합니다."""
    query = request.args.get('artist_query', '').strip()
    results = []
    
    if query:
        # 검색 결과는 artist_results.html로 보내기 위해 여기서 처리합니다.
        db = get_db()
        cursor = db.cursor()
        
        # LIKE 검색으로 데이터 불일치 문제 해결
        search_term = '%' + query.strip() + '%'
        
        cursor.execute(
            "SELECT ranking, title, artist FROM melon_chart_data WHERE artist LIKE ? ORDER BY ranking ASC",
            (search_term,)
        )
        results = cursor.fetchall()
        return render_template('artist_results.html', artist_query=query, results=results)
    
    # 검색어 없이 '/artist-search'에 접속할 때, 검색창만 있는 페이지를 렌더링합니다.
    return render_template('artist-search.html', artist_query='')
    

if __name__ == '__main__':
    init_db() 
    app.run(debug=True, host='0.0.0.0')