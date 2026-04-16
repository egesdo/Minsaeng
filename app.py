import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timedelta
import urllib.parse
import json
import re
from difflib import SequenceMatcher

# --- 1. 기본 설정 (사이드바 미사용 및 와이드 레이아웃) ---
st.set_page_config(page_title="Fin-Light | 통합 대시보드", layout="wide", initial_sidebar_state="collapsed")

# --- 2. 애플 시스템 컬러 및 고정 레이아웃 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp { font-family: 'Pretendard Variable', -apple-system, sans-serif !important; background-color: #FBFBFD !important; }
    
    /* 헤더, 푸터, 사이드바 제어 버튼 숨김 */
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    [data-testid="collapsedControl"] { display: none !important; }
    
    /* 메인 여백 최소화 */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1200px !important; margin: 0 auto !important; }
    
    /* 타이틀 디자인 */
    .header-box { text-align: center; margin-bottom: 25px; }
    .header-title { font-size: 32px; font-weight: 900; color: #1D1D1F; letter-spacing: -1.2px; }
    
    /* 버튼 색상 시스템 (Apple System Colors) */
    /* 1. 메뉴 탭 버튼 (Blue / Gray) */
    .stButton > button[kind="primary"] { background-color: #0071E3 !important; border-radius: 980px !important; color: white !important; font-weight: 600 !important; }
    .stButton > button[kind="secondary"] { background-color: #E8E8ED !important; border-radius: 980px !important; color: #1D1D1F !important; border: none !important; }
    
    /* 2. 실행 버튼 (Indigo/Deep Blue) */
    .run-btn-container .stButton > button { 
        background: linear-gradient(180deg, #5E5CE6 0%, #4845D2 100%) !important; 
        color: white !important; font-size: 17px !important; padding: 0.8rem !important;
        box-shadow: 0 4px 15px rgba(94, 92, 230, 0.3) !important;
    }

    /* 3. 범죄 유형 선택 버튼 (Pill 스타일) */
    .type-btn-active button { background-color: #1D1D1F !important; color: white !important; border-radius: 20px !important; border: none !important; font-size: 13px !important; }
    .type-btn-inactive button { background-color: #FFFFFF !important; color: #86868B !important; border: 1px solid #D2D2D7 !important; border-radius: 20px !important; font-size: 13px !important; }

    /* 입력창 및 카드 디자인 */
    .stTextInput input, .stTextArea textarea { border-radius: 14px !important; border: 1px solid #D2D2D7 !important; }
    .result-card { background-color: #FFFFFF; border: 1px solid #E5E5EA; border-radius: 18px; padding: 22px; margin-bottom: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    .entity-tag { background-color: #F2F2F7; color: #5E5CE6; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; margin-right: 6px; display: inline-block; }
    
    /* 8분할 그리드 */
    .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; gap: 12px; margin-top: 15px; }
    .perfect-grid-item { width: calc(50% - 6px); }
    .perfect-grid iframe { width: 100%; height: 460px; border: 1px solid #E5E5EA; border-radius: 14px; background-color: #FFFFFF; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 상태 관리 및 API ---
if 'active_tab' not in st.session_state: st.session_state.active_tab = "AI"
if 'selected_types' not in st.session_state: st.session_state.selected_types = ["불법사금융"]

def set_tab(t): st.session_state.active_tab = t

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Gemini API 키가 유효하지 않습니다.")
    st.stop()

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "대부중개"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금감원 사칭", "코인 리딩방"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "다단계 코인"]
}

# --- 4. 상단 타이틀 & 메뉴 탭 ---
st.markdown('<div class="header-box"><div class="header-title">Fin-Light</div></div>', unsafe_allow_html=True)

# 메인 탭 선택 (아빠맵 스타일)
col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 2, 3])
with col_t2:
    if st.button("AI 모니터링", use_container_width=True, type="primary" if st.session_state.active_tab == "AI" else "secondary"):
        set_tab("AI")
        st.rerun()
with col_t3:
    if st.button("통합 검색", use_container_width=True, type="primary" if st.session_state.active_tab == "SEARCH" else "secondary"):
        set_tab("SEARCH")
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 모드 1: AI 모니터링
# ==========================================
if st.session_state.active_tab == "AI":
    with st.container():
        st.markdown("#### 범죄 유형 선택")
        # 범죄유형 버튼식 선택 (Pill 스타일)
        type_cols = st.columns(len(CATEGORY_KEYWORDS))
        for i, (name, _) in enumerate(CATEGORY_KEYWORDS.items()):
            is_selected = name in st.session_state.selected_types
            with type_cols[i]:
                st.markdown(f'<div class="{"type-btn-active" if is_selected else "type-btn-inactive"}">', unsafe_allow_html=True)
                if st.button(name, key=f"btn_{name}", use_container_width=True):
                    if is_selected: 
                        if len(st.session_state.selected_types) > 1: st.session_state.selected_types.remove(name)
                    else: st.session_state.selected_types.append(name)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 키워드 및 설정 카드
        with st.expander("🔍 상세 검색 키워드 및 기간 설정", expanded=True):
            merged_kws = []
            for cat in st.session_state.selected_types: merged_kws.extend(CATEGORY_KEYWORDS[cat])
            
            c1, c2 = st.columns([3, 1])
            with c1:
                kw_input = st.text_area("검색 키워드 (쉼표 구분)", value=", ".join(merged_kws), height=80)
            with c2:
                date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
            
            mand_input = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
            
            st.markdown('<div class="run-btn-container">', unsafe_allow_html=True)
            run_btn = st.button("🚀 정밀 분석 및 리포트 생성")
            st.markdown('</div>', unsafe_allow_html=True)

    if run_btn:
        def crawl_naver(query):
            headers = {"User-Agent": "Mozilla/5.0"}
            q = urllib.parse.quote(query)
            # 뉴스 & 뷰탭 크롤링 합산
            res_news = requests.get(f"https://search.naver.com/search.naver?where=news&query={q}", headers=headers, timeout=5)
            soup = BeautifulSoup(res_news.text, 'html.parser')
            items = []
            for li in soup.select('.list_news > li')[:15]:
                tit = li.select_one('.news_tit')
                desc = li.select_one('.api_txt_lines.dsc_txt_wrap')
                if tit: items.append({'category': 'news', 'title': tit.text, 'link': tit['href'], 'desc': desc.text if desc else '', 'source': '네이버 뉴스'})
            return items

        def analyze_ai_relaxed(title, desc):
            # 필터링 강도를 낮춘 프롬프트
            prompt = f"""
            당신은 민생범죄 정보 분석관입니다. 아래 글이 민생범죄(사금융, 리딩방, 사기)와 조금이라도 연관된 실제 사건 기사나 피해 사례라면 'INFO'라고 답하세요. 
            명백한 광고(변호사 수임 광고, 대출 광고)가 아니라면 가급적 노출하는 것이 원칙입니다.
            [출력형식: JSON] {{"status": "INFO" 또는 "AD", "entities": ["코인명", "범인 가명", "플랫폼명"]}}
            제목: {title} / 내용: {desc}
            """
            try:
                r = model.generate_content(prompt)
                res = json.loads(r.text.strip().replace('```json', '').replace('```', ''))
                return res.get("status") == "INFO", res.get("entities", [])
            except: return True, []

        with st.spinner("최신 정보를 수집하고 AI 분석 중입니다..."):
            queries = [f"{k.strip()} {mand_input}" for k in kw_input.split(",")]
            all_data = []
            for q in queries[:6]: # 검색 속도 유지
                all_data.extend(crawl_naver(q))
            
            unique_data = list({it['link']: it for it in all_data}.values())
            
            if not unique_data:
                st.warning("수집된 데이터가 없습니다. 필수 포함 단어를 줄여보세요.")
            else:
                st.info(f"총 {len(unique_data)}건 수집 완료. 정밀 필터링을 시작합니다.")
                count = 0
                for item in unique_data:
                    # 텍스트 하드 필터 완화 (노골적인 단어만 제외)
                    if any(kw in item['title'] for kw in ["무료 법률 상담", "무료 상담 신청"]): continue
                    
                    is_info, entities = analyze_ai_relaxed(item['title'], item['desc'])
                    if is_info:
                        count += 1
                        st.markdown(f"""
                        <div class="result-card">
                            <div style="color:#5E5CE6; font-weight:bold; margin-bottom:6px;">[정보 수집 완료]</div>
                            <div style="font-size:19px; font-weight:700; margin-bottom:12px;"><a href="{item['link']}" target="_blank" style="color:#1D1D1F; text-decoration:none;">{item['title']}</a></div>
                            {" ".join([f"<span class='entity-tag'># {e}</span>" for e in entities])}
                            <div style="color:#636366; font-size:14px; margin-top:15px; line-height:1.6;">{item['desc'][:200]}...</div>
                            <div style="color:#86868B; font-size:12px; margin-top:10px;">출처: {item['source']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                if count == 0:
                    st.error("AI 분석 결과, 유효한 정보가 없습니다. 검색어를 더 넓게 설정해보세요.")

# ==========================================
# 모드 2: 통합 검색 (8분할)
# ==========================================
else:
    st.markdown('<div style="background-color:#FFFFFF; padding:25px; border-radius:20px; border:1px solid #E5E5EA; box-shadow: 0 4px 12px rgba(0,0,0,0.02);">', unsafe_allow_html=True)
    with st.form("search_form"):
        sc1, sc2 = st.columns([8, 2])
        with sc1:
            q_input = st.text_input("포털 및 커뮤니티 통합 검색어", placeholder="예: 선이자 연장비 송치", label_visibility="collapsed")
        with sc2:
            st.markdown('<div class="run-btn-container">', unsafe_allow_html=True)
            s_btn = st.form_submit_button("🚀 8분할 검색")
            st.markdown('</div>', unsafe_allow_html=True)
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
                <div style="font-weight:700; font-size:14px; margin-bottom:10px; padding-left:5px; color:#1D1D1F;">{labels[i]}</div>
                <iframe src="{urls[i]}"></iframe>
            </div>'''
        grid_html += '</div>'
        st.markdown(grid_html, unsafe_allow_html=True)
