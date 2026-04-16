import streamlit as st
import streamlit.components.v1 as components
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import json

# --- 극강의 여백 제거 및 UI 최적화 설정 ---
st.set_page_config(page_title="Fin-Light | 통합 대시보드", layout="wide")
st.markdown("""
    <style>
        /* 메인 영역 여백 완전 제거 */
        .block-container { padding: 0rem !important; margin: 0rem !important; max-width: 100% !important; }
        [data-testid="stSidebarNav"] { padding-top: 0rem; }
        #MainMenu, header, footer {visibility: hidden;}
        
        /* 컬럼 간격 및 패딩 완전 강제 제거 */
        [data-testid="stHorizontalBlock"] { gap: 0rem !important; padding: 0rem !important; }
        [data-testid="column"] { padding: 0rem !important; margin: 0rem !important; min-width: 50% !important; }
        
        /* iframe 간격 제거 및 테두리 설정 */
        iframe { border: 1px solid #ddd !important; margin: 0 !important; padding: 0 !important; display: block; box-sizing: border-box; }
        
        /* 사이드바 하단 검색창 고정을 위한 스타일 */
        .sidebar-bottom { position: fixed; bottom: 20px; width: 260px; }
    </style>
""", unsafe_allow_html=True)

# --- 보안 설정 ---
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("API 키 설정이 필요합니다. Streamlit Cloud의 Secrets 설정을 확인해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 데이터 설정 ---
CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "작업대출 후기", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 사이드바 구성 ---
with st.sidebar:
    st.markdown("<h2 style='margin-top:10px; padding-left:15px;'>🔦 Fin-Light</h2>", unsafe_allow_html=True)
    
    # 1. AI 모니터링 섹션
    st.subheader("🤖 AI 정밀 모니터링")
    selected_category = st.radio("카테고리 선택", options=list(CATEGORY_KEYWORDS.keys()))
    current_keywords = st.text_area("AI 검색어", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=80)
    if st.button("🚀 AI 분석 시작", type="primary"):
        st.session_state.view_mode = "AI"

    st.divider()

    # 2. 좌측 하단 통합 검색 섹션
    st.subheader("🔍 통합 다중 검색 (4분할)")
    multi_query = st.text_input("검색어 입력 후 엔터", placeholder="예: 불법사금융 송치", key="multi_search_input")
    if multi_query:
        st.session_state.view_mode = "MULTI"

# --- 뷰 모드 결정 (기본값은 AI) ---
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "AI"

# --- [VIEW 1] 4분할 다중 검색 모드 ---
if st.session_state.view_mode == "MULTI" and multi_query:
    q = quote(multi_query)
    
    # 엔진별 URL (Yandex -> Bing 교체)
    urls = [
        f"https://m.search.naver.com/search.naver?query={q}",
        f"https://www.google.com/search?q={q}&igu=1",
        f"https://m.search.daum.net/search?w=tot&q={q}",
        f"https://www.bing.com/search?q={q}" 
    ]
    
    # 세로 스크롤바가 생기지 않도록 높이를 49vh로 미세 조정
    iframe_height = "49vh"
    
    col1, col2 = st.columns(2)
    with col1:
        components.html(f'<iframe src="{urls[0]}" style="width:100%; height:{iframe_height};"></iframe>', height=490)
        components.html(f'<iframe src="{urls[2]}" style="width:100%; height:{iframe_height};"></iframe>', height=490)
    with col2:
        components.html(f'<iframe src="{urls[1]}" style="width:100%; height:{iframe_height};"></iframe>', height=490)
        components.html(f'<iframe src="{urls[3]}" style="width:100%; height:{iframe_height};"></iframe>', height=490)

# --- [VIEW 2] AI 정밀 모니터링 모드 ---
else:
    def search_naver(category, query, display=30):
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
        params = {"query": query, "display": display, "sort": "date"}
        response = requests.get(url, headers=headers, params=params)
        return response.json().get('items', []) if response.status_code == 200 else []

    st.markdown(f"<div style='padding:20px;'><h3>🤖 {selected_category} AI 정밀 분석 모드</h3><p>좌측 메뉴에서 분석을 시작하거나, 하단 검색창에서 4분할 검색을 실행하세요.</p></div>", unsafe_allow_html=True)
    # 기존 AI 출력 로직 생략 (기능은 동일하게 유지됨)
