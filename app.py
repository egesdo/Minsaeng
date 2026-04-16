import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timedelta
import urllib.parse
import json
import re
from difflib import SequenceMatcher

# --- 1. 기본 설정 (사이드바 미사용을 위해 레이아웃 고정) ---
st.set_page_config(page_title="Fin-Light | 통합 모니터링", layout="wide", initial_sidebar_state="collapsed")

# --- 2. 애플 스타일 & 상단 메뉴 최적화 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp { font-family: 'Pretendard Variable', -apple-system, sans-serif !important; background-color: #FBFBFD !important; }
    
    /* 헤더, 푸터, 사이드바 버튼 등 모든 불필요 요소 제거 */
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    [data-testid="collapsedControl"] { display: none !important; }
    
    /* 메인 컨테이너 중앙 정렬 및 여백 최적화 */
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 1200px !important; margin: 0 auto !important; }
    
    /* 상단 애플 스타일 타이틀 박스 */
    .header-box { text-align: center; margin-bottom: 30px; }
    .header-title { font-size: 32px; font-weight: 900; color: #1D1D1F; letter-spacing: -1px; margin-bottom: 5px; }
    
    /* 아빠맵 스타일 상단 탭 (Pill 형태) */
    .tab-container { display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; }
    
    /* 카드 및 입력창 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div { border-radius: 14px !important; border: 1px solid #D2D2D7 !important; background-color: #FFFFFF !important; }
    
    /* 실행 버튼 스타일 */
    .stButton > button { 
        border-radius: 980px !important; 
        background-color: #0071E3 !important; 
        color: #FFFFFF !important; 
        border: none !important; 
        font-weight: 700 !important; 
        padding: 0.7rem 2rem !important;
        box-shadow: 0 4px 12px rgba(0, 113, 227, 0.2) !important;
    }
    .stButton > button:hover { background-color: #0077ED !important; }

    /* 결과 카드 디자인 */
    .result-card { background-color: #FFFFFF; border: 1px solid #E5E5EA; border-radius: 16px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
    .entity-tag { background-color: #F2F2F7; color: #0071E3; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; margin-right: 6px; display: inline-block; }
    
    /* 8분할 그리드 */
    .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; gap: 15px; margin-top: 20px; }
    .perfect-grid-item { width: calc(50% - 8px); }
    .perfect-grid iframe { width: 100%; height: 450px; border: 1px solid #E5E5EA; border-radius: 12px; background-color: #FFFFFF; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 상태 관리 및 API 설정 ---
if 'active_tab' not in st.session_state: st.session_state.active_tab = "AI"

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets 설정에서 GEMINI_API_KEY를 입력해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "대부중개사이트"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금감원 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "다단계 코인"]
}

# --- 4. 상단 헤더 & 아빠맵 스타일 메뉴 ---
st.markdown('<div class="header-box"><div class="header-title">Fin-Light</div></div>', unsafe_allow_html=True)

col_m1, col_m2, col_m3, col_m4 = st.columns([3, 2, 2, 3])
with col_m2:
    if st.button("AI 모니터링", use_container_width=True, type="primary" if st.session_state.active_tab == "AI" else "secondary"):
        st.session_state.active_tab = "AI"
        st.rerun()
with col_m3:
    if st.button("통합 검색", use_container_width=True, type="primary" if st.session_state.active_tab == "SEARCH" else "secondary"):
        st.session_state.active_tab = "SEARCH"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 모드 1: AI 모니터링
# ==========================================
if st.session_state.active_tab == "AI":
    # 설정 영역을 카드 형태로 상단에 배치
    with st.expander("⚙️ 분석 조건 설정", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            selected_cats = st.multiselect("범죄 유형", options=list(CATEGORY_KEYWORDS.keys()), default=["불법사금융"])
        with c2:
            date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
        
        merged_kws = []
        for cat in selected_cats: merged_kws.extend(CATEGORY_KEYWORDS[cat])
        
        kw_input = st.text_area("검색 키워드 (쉼표 구분)", value=", ".join(merged_kws), height=80)
        mand_input = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
        
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        run_btn = st.button("🚀 정밀 분석 실행")
        st.markdown("</div>", unsafe_allow_html=True)

    if run_btn:
        # (기존 크롤링 및 AI 분석 로직 함수들 - 생략 방지를 위해 핵심만 포함)
        def crawl_naver(query):
            headers = {"User-Agent": "Mozilla/5.0"}
            q = urllib.parse.quote(query)
            res = requests.get(f"https://search.naver.com/search.naver?where=news&query={q}", headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            items = []
            for li in soup.select('.list_news > li')[:15]:
                tit = li.select_one('.news_tit')
                if tit: items.append({'category': 'news', 'title': tit.text, 'link': tit['href'], 'source': '뉴스', 'raw_date': '최근'})
            return items

        def analyze_ai(title):
            prompt = f"금융범죄 분석: {{'status': 'INFO'}}. 제목: {title}"
            try:
                r = model.generate_content(prompt)
                return "INFO" in r.text.upper(), []
            except: return True, []

        with st.spinner("최신 정보를 수집하고 분석 중입니다..."):
            queries = [f"{k.strip()} {mand_input}" for k in kw_input.split(",")]
            all_data = []
            for q in queries[:5]: # 속도를 위해 쿼리 제한
                all_data.extend(crawl_naver(q))
            
            unique_data = list({it['link']: it for it in all_data}.values())
            
            if not unique_data:
                st.warning("수집된 데이터가 없습니다.")
            else:
                st.success(f"총 {len(unique_data)}건의 정보를 발견했습니다.")
                for item in unique_data:
                    is_v, ent = analyze_ai(item['title'])
                    if is_v:
                        st.markdown(f"""
                        <div class="result-card">
                            <div style="color:#0071E3; font-weight:bold; margin-bottom:5px;">[NEWS]</div>
                            <div style="font-size:18px; font-weight:700; margin-bottom:10px;"><a href="{item['link']}" style="color:#1D1D1F; text-decoration:none;">{item['title']}</a></div>
                            <div style="color:#86868B; font-size:14px;">출처: {item['source']}</div>
                        </div>
                        """, unsafe_allow_html=True)

# ==========================================
# 모드 2: 통합 검색 (8분할)
# ==========================================
else:
    st.markdown("<div style='background-color:#FFFFFF; padding:25px; border-radius:18px; border:1px solid #E5E5EA;'>", unsafe_allow_html=True)
    with st.form("search_form"):
        sc1, sc2 = st.columns([8, 2])
        with sc1:
            q_input = st.text_input("검색어를 입력하세요", placeholder="예: 불법사금융 송치", label_visibility="collapsed")
        with sc2:
            s_btn = st.form_submit_button("🚀 8분할 검색")
    st.markdown("</div>", unsafe_allow_html=True)

    if s_btn and q_input:
        q = urllib.parse.quote(q_input)
        q_dc = urllib.parse.quote(f"site:gall.dcinside.com {q_input}")
        q_fm = urllib.parse.quote(f"site:fmkorea.com {q_input}")
        
        urls = [
            f"https://m.search.naver.com/search.naver?query={q}",
            f"https://www.google.com/search?q={q}&igu=1",
            f"https://m.search.daum.net/search?w=tot&q={q}",
            f"https://www.bing.com/search?q={q}",
            f"https://www.google.com/search?q={q_dc}&igu=1",
            f"https://www.google.com/search?q={q_fm}&igu=1",
            f"https://www.google.com/search?q={urllib.parse.quote('site:bbs.ruliweb.com ' + q_input)}&igu=1",
            f"https://www.google.com/search?q={urllib.parse.quote('site:clien.net ' + q_input)}&igu=1"
        ]
        labels = ["🟢 네이버", "🔵 구글", "🟡 다음", "🌐 빙", "🟦 디시인사이드", "🟦 에펨코리아", "🟦 루리웹", "🟦 클리앙"]
        
        grid_html = '<div class="perfect-grid">'
        for i in range(8):
            grid_html += f'''
            <div class="perfect-grid-item">
                <div style="font-weight:bold; margin-bottom:8px; padding-left:5px;">{labels[i]}</div>
                <iframe src="{urls[i]}"></iframe>
            </div>'''
        grid_html += '</div>'
        st.markdown(grid_html, unsafe_allow_html=True)
