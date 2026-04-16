import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timedelta
import urllib.parse
import json
import re
from difflib import SequenceMatcher

# --- 1. 기본 설정 ---
st.set_page_config(page_title="Fin-Light | 모니터링 시스템", layout="wide", initial_sidebar_state="expanded")

# --- 2. 최적화된 애플 스타일 CSS 및 사이드바 버튼 강제 삭제 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp { font-family: 'Pretendard Variable', -apple-system, sans-serif !important; background-color: #FBFBFD !important; }
    
    /* 거슬리는 UI 요소 완벽 제거 */
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    
    /* 🚨 사이드바 접기(<<) 및 펼치기(>) 버튼 영구 삭제 (모든 가능한 속성 타겟팅) 🚨 */
    [data-testid="collapsedControl"] { display: none !important; width: 0px !important; height: 0px !important; pointer-events: none !important; }
    button[kind="header"] { display: none !important; }
    
    /* 사이드바 여백 완전 제거 및 고정 */
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E5E5EA !important; min-width: 320px !important; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0rem !important; }
    
    /* 메인 컨테이너 여백 축소 */
    .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; max-width: 1200px !important; }
    
    /* 입력창 및 공통 버튼 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div { border-radius: 12px !important; border: 1px solid #D2D2D7 !important; }
    
    /* 실행 버튼 스타일 */
    .stButton > button { 
        border-radius: 980px !important; 
        background-color: #0071E3 !important; 
        color: #FFFFFF !important; 
        border: none !important; 
        font-weight: 700 !important; 
        font-size: 16px !important;
        width: 100%; 
        padding: 0.8rem !important; 
        box-shadow: 0 4px 12px rgba(0, 113, 227, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover { background-color: #0077ED !important; transform: scale(0.98); }
    
    /* 타이틀 박스 */
    .apple-title-box { background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%); border-bottom: 1px solid #E5E5EA; padding: 25px 20px 20px 20px; text-align: center; margin-bottom: 15px; margin-top:-1rem; margin-left:-1rem; margin-right:-1rem; }
    .apple-title-text { font-size: 24px; font-weight: 900; color: #1D1D1F; letter-spacing: -0.5px; }
    
    /* 엔티티 및 결과 카드 디자인 */
    .entity-tag { background-color: #E6F3FF; color: #0066CC; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; margin-right: 6px; margin-bottom: 6px; display: inline-block; }
    .result-card { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 10px; padding: 16px; margin-top: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }
    
    /* 8분할 화면용 그리드 */
    .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; gap: 10px; margin-top: 10px; }
    .perfect-grid iframe { width: calc(50% - 5px); height: 45vh; border: 1px solid #E5E5EA; border-radius: 8px; box-sizing: border-box; background-color: #FFFFFF; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 상태 관리 ---
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "AI_MODE"

def set_tab(tab_name):
    st.session_state.active_tab = tab_name

# --- 4. API 및 기본 데이터 설정 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("⚠️ Secrets 설정에서 GEMINI_API_KEY를 입력해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 5. 사이드바 구성 ---
with st.sidebar:
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text">Fin-Light</div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        is_ai = st.session_state.active_tab == "AI_MODE"
        st.button("AI 모니터링", on_click=set_tab, args=("AI_MODE",), type="primary" if is_ai else "secondary", use_container_width=True)
    with col2:
        is_search = st.session_state.active_tab == "SEARCH_MODE"
        st.button("통합 검색", on_click=set_tab, args=("SEARCH_MODE",), type="primary" if is_search else "secondary", use_container_width=True)
    
    st.divider()

    if st.session_state.active_tab == "AI_MODE":
        run_btn = st.button("🚀 정밀 분석 실행")
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("<h4 style='font-size:15px; color:#1D1D1F;'>⚙️ 분석 설정</h4>", unsafe_allow_html=True)
        st.write("범죄 유형 (다중 선택)")
        
        selected_categories = []
        for cat in CATEGORY_KEYWORDS.keys():
            if st.checkbox(cat, value=(cat == "불법사금융")):
                selected_categories.append(cat)
                
        default_kws = []
        for cat in selected_categories:
            default_kws.extend(CATEGORY_KEYWORDS[cat])
            
        current_keywords = st.text_area("검색어 (쉼표 구분)", value=", ".join(default_kws), height=80)
        mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
        date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
        
    else:
        st.markdown("<h4 style='font-size:15px; color:#1D1D1F;'>🔍 8분할 검색 설정</h4>", unsafe_allow_html=True)
        with st.form("multi_search_form"):
            multi_query = st.text_input("검색어", placeholder="예: 불법사금융 송치", label_visibility="collapsed")
            search_submitted = st.form_submit_button("🚀 검색 실행")

# ==========================================
# 메인 화면: AI 정밀 분석 모드
# ==========================================
if st.session_state.active_tab == "AI_MODE":
    st.header("🤖 AI 정밀 분석 대시보드")
    st.caption("네이버 검색 결과를 크롤링하여 AI가 핵심 정보를 추출하고 노이즈를 제거합니다.")

    if 'run_btn' in locals() and run_btn:
        if not selected_categories:
            st.error("최소 한 개의 범죄 유형을 선택해주세요.")
            st.stop()
            
        def parse_korean_date(date_str):
            now = datetime.now()
            if not date_str: return now
            if any(x in date_str for x in ['시간', '분', '초']): return now
            if '일 전' in date_str:
                days = int(re.search(r'\d+', date_str).group())
                return now - timedelta(days=days)
            if '어제' in date_str: return now - timedelta(days=1)
            match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
            if match: return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return now

        def crawl_naver(query):
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            encoded_query = urllib.parse.quote(query)
            results = []
            try:
                res = requests.get(f"https://search.naver.com/search.naver?where=news&query={encoded_query}", headers=headers, timeout=5)
                soup = BeautifulSoup(res.text, 'html.parser')
                for li in soup.select('.list_news > li'):
                    tit = li.select_one('.news_tit')
                    desc = li.select_one('.api_txt_lines.dsc_txt_wrap')
                    press = li.select_one('.info_group > a.info.press')
                    date_tag = li.select_one('.info_group > span.info')
                    if tit:
                        results.append({'category': 'news', 'title': tit.text, 'link': tit['href'], 'desc': desc.text if desc else '', 'source': press.text.replace("언론사 선정", "") if press else '언론사', 'raw_date': date_tag.text if date_tag else ''})
            except: pass
                
            try:
                res = requests.get(f"https://search.naver.com/search.naver?where=view&query={encoded_query}", headers=headers, timeout=5)
                soup = BeautifulSoup(res.text, 'html.parser')
                for li in soup.select('.lst_view > li, .view_wrap'):
                    tit = li.select_one('.title_link')
                    desc = li.select_one('.dsc_txt')
                    user = li.select_one('.name')
                    date_tag = li.select_one('.sub_time')
                    if tit:
                        cat = 'cafearticle' if 'cafe.naver' in tit['href'] else 'blog'
                        results.append({'category': cat, 'title': tit.text, 'link': tit['href'], 'desc': desc.text if desc else '', 'source': user.text if user else '블로거/카페', 'raw_date': date_tag.text if date_tag else ''})
            except: pass
            return results

        def analyze_with_gemini(title, desc):
            prompt = f"금융범죄 분석: {{'status': 'INFO' 또는 'AD', 'entities': ['코인명', '플랫폼명', '가명']}}. INFO: 실제사건/피해호소, AD: 법무법인광고/단순교육. 제목: {title}, 내용: {desc}"
            try:
                res = model.generate_content(prompt)
                res_json = json.loads(res.text.strip().replace('```json', '').replace('```', ''))
                return res_json.get("status") == "INFO", res_json.get("entities", [])
            except: return True, [] 

        def get_badge(cat):
            if cat == 'news': return "🔵 **[뉴스]**"
            elif cat == 'blog': return "🟢 **[블로그]**"
            return "🔴 **[카페]**"

        now = datetime.now()
        if date_filter == "최근 1개월": limit_date = now - timedelta(days=30)
        elif date_filter == "최근 3개월": limit_date = now - timedelta(days=90)
        elif date_filter == "최근 1년": limit_date = now - timedelta(days=365)
        else: limit_date = None

        raw_results = []
        base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
        mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
        
        with st.spinner("데이터를 수집하고 AI로 분석 중입니다..."):
            search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

            for query in search_queries:
                crawled_items = crawl_naver(query)
                for item in crawled_items:
                    if any(kw in (item['title'] + item['desc']) for kw in ["법무법인", "변호사", "수임료", "승소", "고소대리", "무료상담"]): continue
                    dt_obj = parse_korean_date(item['raw_date'])
                    if limit_date and dt_obj < limit_date: continue
                    item.update({'datetime': dt_obj, 'date_str': dt_obj.strftime("%Y-%m-%d")})
                    raw_results.append(item)

            unique_results = sorted(list({it['link']: it for it in raw_results}.values()), key=lambda x: x['datetime'], reverse=True)
            
            valid_results = []
            for item in unique_results[:30]: 
                is_valid, entities = analyze_with_gemini(item['title'], item['desc'])
                if is_valid:
                    item['entities'] = entities
                    valid_results.append(item)

            grouped_results = []
            for item in valid_results:
                found = False
                for group in grouped_results:
                    if SequenceMatcher(None, item['title'], group[0]['title']).ratio() > 0.5:
                        group.append(item); found = True; break
                if not found: grouped_results.append([item])

            st.divider()
            if not grouped_results:
                st.warning("조건에 맞는 유효한 데이터가 없습니다.")
            else:
                st.success(f"분석 완료! 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
                for group in grouped_results:
                    main = group[0]
                    with st.container():
                        st.markdown(f"#### {get_badge(main['category'])} [{main['title']}]({main['link']})")
                        col1, col2 = st.columns([8, 2])
                        with col1:
                            if main.get('entities'): st.markdown("".join([f"<span class='entity-tag'># {e}</span>" for e in main['entities']]), unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"<div style='text-align:right; font-size:14px; color:#86868B;'>{main['date_str']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='result-card'><b>출처: {main['source']}</b><br><span style='color:#555;'>{main['desc']}</span></div>", unsafe_allow_html=True)
                        if len(group) > 1:
                            with st.expander(f"🔗 비슷한 내용의 기사/게시글 {len(group)-1}개 더보기"):
                                for sub in group[1:]:
                                    st.markdown(f"- {get_badge(sub['category'])} [{sub['title']}]({sub['link']}) ({sub['source']} / {sub['date_str']})")

# ==========================================
# 메인 화면: 통합 검색 (8분할)
# ==========================================
elif st.session_state.active_tab == "SEARCH_MODE":
    st.header("🌐 통합 검색 대시보드 (8분할)")
    st.caption("포털 사이트와 주요 커뮤니티의 검색 결과를 한 화면에서 비교합니다.")
    
    if 'search_submitted' in locals() and search_submitted and multi_query:
        q = urllib.parse.quote(multi_query)
        q_dc = urllib.parse.quote(f"site:gall.dcinside.com {multi_query}")
        q_fm = urllib.parse.quote(f"site:fmkorea.com {multi_query}")
        q_ruli = urllib.parse.quote(f"site:bbs.ruliweb.com {multi_query}")
        q_clien = urllib.parse.quote(f"site:clien.net {multi_query}")
        
        urls = [
            f"https://m.search.naver.com/search.naver?query={q}",
            f"https://m.search.daum.net/search?w=tot&q={q}",
            f"https://www.google.com/search?q={q}&igu=1",
            f"https://www.bing.com/search?q={q}",
            f"https://www.google.com/search?q={q_dc}&igu=1",
            f"https://www.google.com/search?q={q_fm}&igu=1",
            f"https://www.google.com/search?q={q_ruli}&igu=1",
            f"https://www.google.com/search?q={q_clien}&igu=1"
        ]
        
        st.markdown(f"""
            <div class="perfect-grid">
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#03C75A; margin-bottom:5px;">🟢 네이버</div><iframe src="{urls[0]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#FFCD00; margin-bottom:5px;">🟡 다음</div><iframe src="{urls[1]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#4285F4; margin-bottom:5px;">🔵 구글</div><iframe src="{urls[2]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#0078D7; margin-bottom:5px;">🌐 Bing</div><iframe src="{urls[3]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#3B4890; margin-bottom:5px;">🟦 디시인사이드</div><iframe src="{urls[4]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#1E3A8A; margin-bottom:5px;">🟦 에펨코리아</div><iframe src="{urls[5]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#1D4ED8; margin-bottom:5px;">🟦 루리웹</div><iframe src="{urls[6]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
                <div style="width: calc(50% - 5px);"><div style="font-weight:bold; color:#2563EB; margin-bottom:5px;">🟦 클리앙</div><iframe src="{urls[7]}" style="width:100%; height:45vh; border: 1px solid #E5E5EA; border-radius: 8px;"></iframe></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("좌측 사이드바 하단에서 검색어를 입력하고 실행 버튼을 눌러주세요.")
