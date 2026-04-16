import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import json

# --- 애플 스타일 UI 및 강제 여백 제거 CSS ---
st.set_page_config(page_title="Fin-Light | 통합 대시보드", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
        /* 1. 폰트 및 전체 배경 (Apple 스타일) */
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        html, body, [class*="css"], .stApp {
            font-family: 'Pretendard Variable', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif !important;
            background-color: #FBFBFD !important; /* 애플 특유의 밝은 회색 배경 */
        }
        
        /* 2. 거슬리는 워터마크 및 헤더/푸터 완벽 제거 */
        header[data-testid="stHeader"] { display: none !important; } /* 상단 깃허브, 햄버거 메뉴 제거 */
        footer { display: none !important; } /* 하단 스트림릿 로고 제거 */
        .stDeployButton { display: none !important; } /* Deploy 버튼 제거 */
        #MainMenu { display: none !important; }
        
        /* 3. 화면 잘림 현상 해결 (메인 컨테이너 여백 0 강제화) */
        .block-container {
            padding: 0rem !important;
            margin: 0rem !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        
        /* 4. 사이드바 상단 여백 제거 및 디자인 */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E5E5EA !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.5rem !important; /* 사이드바 상단 여백 최소화 */
        }
        
        /* 5. Apple 스타일 입력창 및 버튼 */
        .stTextInput input, .stTextArea textarea {
            border-radius: 10px !important;
            border: 1px solid #D2D2D7 !important;
            transition: all 0.2s ease;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #0071E3 !important;
            box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
        }
        .stButton > button {
            border-radius: 980px !important; /* 둥근 캡슐형 버튼 */
            background-color: #0071E3 !important;
            color: #FFFFFF !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 2px 5px rgba(0,113,227,0.3) !important;
        }
        .stButton > button:hover {
            background-color: #0077ED !important;
            transform: scale(0.98);
        }

        /* 6. Fin-Light 타이틀 박스 (Glassmorphism 효과) */
        .apple-title-box {
            background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%);
            border: 1px solid #E5E5EA;
            border-radius: 16px;
            padding: 18px 15px;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        }
        .apple-title-text {
            font-size: 22px;
            font-weight: 800;
            color: #1D1D1F;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .apple-subtitle-text {
            font-size: 11px;
            color: #86868B;
            margin-top: 4px;
            font-weight: 500;
        }

        /* 7. 4분할 화면 완벽 매칭을 위한 커스텀 그리드 */
        .perfect-grid {
            display: flex;
            flex-wrap: wrap;
            width: 100%;
            height: 100vh; /* 화면 높이 100% 꽉 채움 */
        }
        .perfect-grid iframe {
            width: 50%;
            height: 50vh; /* 정확히 절반씩 배분 */
            border: 1px solid #E5E5EA;
            border-top: none;
            border-left: none;
            box-sizing: border-box;
            background-color: #FFFFFF;
        }
    </style>
""", unsafe_allow_html=True)

# --- 보안 및 API 설정 ---
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("API 키 설정이 필요합니다.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "작업대출 후기", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 사이드바 구성 ---
with st.sidebar:
    # 세련된 타이틀 박스 삽입
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text"><span>🔦</span> Fin-Light</div>
            <div class="apple-subtitle-text">민생금융범죄 모니터링 대시보드</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🤖 AI 정밀 모니터링</h4>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리", options=list(CATEGORY_KEYWORDS.keys()), label_visibility="collapsed")
    current_keywords = st.text_area("AI 검색어", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
    
    if st.button("AI 분석 시작"):
        st.session_state.view_mode = "AI"

    st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🔍 통합 다중 검색 (4분할)</h4>", unsafe_allow_html=True)
    multi_query = st.text_input("검색어 입력 후 엔터", placeholder="예: 선이자", key="multi_search_input")
    
    if multi_query:
        st.session_state.view_mode = "MULTI"

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "AI"

# --- [VIEW 1] 4분할 다중 검색 모드 (스트림릿 레이아웃 무시) ---
if st.session_state.view_mode == "MULTI" and multi_query:
    q = quote(multi_query)
    
    urls = [
        f"https://m.search.naver.com/search.naver?query={q}",
        f"https://www.google.com/search?q={q}&igu=1",
        f"https://m.search.daum.net/search?w=tot&q={q}",
        f"https://www.bing.com/search?q={q}"
    ]
    
    # 스트림릿의 컬럼(columns) 기능을 아예 사용하지 않고, HTML로 화면을 직접 그립니다.
    # 이렇게 해야 잘림 현상과 여백 문제를 100% 해결할 수 있습니다.
    html_code = f"""
        <div class="perfect-grid">
            <iframe src="{urls[0]}"></iframe>
            <iframe src="{urls[1]}"></iframe>
            <iframe src="{urls[2]}"></iframe>
            <iframe src="{urls[3]}"></iframe>
        </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

# --- [VIEW 2] AI 정밀 모니터링 모드 ---
else:
    def search_naver(category, query, display=30):
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
        params = {"query": query, "display": display, "sort": "date"}
        response = requests.get(url, headers=headers, params=params)
        return response.json().get('items', []) if response.status_code == 200 else []

    st.markdown(f"<div style='padding:30px;'><h2>🤖 {selected_category} AI 정밀 분석 모드</h2><p style='color:#86868B;'>좌측 메뉴에서 분석을 시작하거나, 하단 검색창에서 4분할 검색을 실행하세요.</p></div>", unsafe_allow_html=True)
    # 기존 AI 출력 로직 생략
