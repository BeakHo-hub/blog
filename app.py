from flask import Flask, render_template, request
import requests
import json
from urllib.parse import quote

# 1. Flask 애플리케이션을 한 번만 초기화합니다.
app = Flask(__name__)

# ★★★ 네이버 개발자 센터에서 발급받은 본인의 Client ID와 Client Secret으로 교체하세요 ★★★
# 이 값들을 채워넣어야 API 호출이 정상적으로 작동합니다.
NAVER_CLIENT_ID = "zQzxVxLPdlCs7JSDPAno" # 예: 'AbcdefghIjKlmnOpQrSt'
NAVER_CLIENT_SECRET = "X_KmE2C_Et" # 예: '1234567890'

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
            # 실패 시 상태 코드 출력 및 빈 리스트 반환
            print(f"API 호출 실패: {response.status_code}")
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
    search_query = request.args.get('query', '')
    
    results = []
    if search_query:
        # 검색어가 있을 경우에만 API 호출
        results = search_naver_blog(search_query)

    # index.html 템플릿 렌더링
    return render_template('index.html', query=search_query, results=results)

if __name__ == '__main__':
    # 2. 통합된 Flask 앱을 실행합니다.
    if NAVER_CLIENT_ID == "YOUR_CLIENT_ID":
        print("경고: NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 값을 본인의 것으로 교체해주세요!")
    
    app.run(debug=True)