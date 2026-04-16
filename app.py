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

# --- 2. 애플 스타일 CSS 및 레이아웃 강제 최적화 ---
custom_css = """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp { font-family: 'Pretendard Variable', -apple-system, sans-serif !important; background-color: #FBFBFD !important; }
    
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    
    /* 사이드바 상단 여백 완벽 제거 */
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E5E5EA !important; }
    
    /* 메인 화면 상하단 여백 축소 */
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    
    /* 입력창 및 공통 버튼 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div { border-radius: 10px !important; border: 1px solid #D2D2D7 !important; }
    .stButton > button { border-radius: 12px !important; background-color: #0071E3 !important; color: #FFFFFF !important; border: none !important; font-weight: 600 !important; width: 100%; padding: 0.6rem !important; }
    .stButton > button:hover { background-color: #0077ED !important; transform: scale(0.98); }
    
    /* Fin-Light 애플 스타일 타이틀 박스 */
    .apple-title-box { background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%); border: 1px solid #E5E5EA; border-radius: 16px; padding: 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03); }
    .apple-title-text { font-size: 20px; font-weight: 800; color: #1D1D1F; letter-spacing: -0.5px; }
    .apple-subtitle-text { font-size: 11px; color: #86868B; margin-top: 4px; }
    
    /* 메뉴(라디오 버튼)를 최신식 좌우 탭 스타일(Segmented Control)로 변경 */
    div[role="radiogroup"] { display: flex; flex-direction: row; background-color: #F0F0F3; border-radius: 10px; padding: 4px; gap: 4px; }
    div[role="radiogroup"] > label { flex: 1; text-align: center; justify-content: center; background-color: transparent; border-radius: 8px; padding: 6px 0; margin: 0; cursor: pointer; transition: all 0.2s ease; }
    div[role="radiogroup"] > label[data-checked="true"] { background-color: #FFFFFF; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-weight: bold; color: #1D1D1F; }
    div[role="radiogroup"] circle { display: none; } /* 기존 라디오 동그라미 숨김 */
    div[role="radiogroup"] p { font-size: 14px; margin: 0; }
    
    /* 엔티티 및 결과 카드 디자인 */
    .entity-tag { background-color: #E8F0FE; color: #1967D2; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-right: 5px; margin-bottom: 5px; display: inline-block; }
    .result-card { background-color: #FFFFFF; border: 1px solid #E5E5EA; border-radius: 12px; padding: 15px; margin-top: 8px; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.02); }
    
    /* 4분할 화면용 그리드 */
    .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; height: 80vh; margin-top: 10px; }
    .perfect-grid iframe { width: 50%; height: 40vh; border: 1px solid #E5E5EA; box-sizing: border-box; background-color: #FFFFFF; }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- 3. API 설정 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("⚠️ Streamlit Cloud의 Secrets 설정에서 GEMINI_API_KEY를 입력해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 4. 사이드바 구성 ---
with st.sidebar:
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text">Fin-Light</div>
            <div class="apple-subtitle-text">민생금융범죄 모니터링 시스템</div>
        </div>
    """, unsafe_allow_html=True)
    
    page = st.radio("메뉴 선택", ["AI 모니터링", "통합검색"], label_visibility="collapsed")
    st.divider()

# ==========================================
# 기능 1 : AI 모니터링
# ==========================================
if page == "AI 모니터링":
    with st.sidebar:
        st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>⚙️ 분석 설정</h4>", unsafe_allow_html=True)
        
        # 라디오 버튼 대신 체크박스 적용
        st.write("범죄 유형 (다중 선택 가능)")
        selected_categories = []
        for cat in CATEGORY_KEYWORDS.keys():
            if st.checkbox(cat, value=(cat == "불법사금융")):
                selected_categories.append(cat)
                
        # 선택된 카테고리의 키워드를 모두 병합
        default_kws = []
        for cat in selected_categories:
            default_kws.extend(CATEGORY_KEYWORDS[cat])
            
        current_keywords = st.text_area("검색어 (쉼표 구분)", value=", ".join(default_kws), height=100)
        mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
        date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
        
        run_btn = st.button("정밀 분석 실행")

    st.header("AI 정밀 분석 대시보드")
    st.caption("네이버 실제 검색 결과를 크롤링하여 AI가 텍스트를 분석하고 핵심 정보를 추출합니다.")

    if run_btn:
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
                        results.append({
                            'category': 'news', 'title': tit.text, 'link': tit['href'],
                            'desc': desc.text if desc else '', 'source': press.text.replace("언론사 선정", "") if press else '언론사',
                            'raw_date': date_tag.text if date_tag else ''
                        })
            except Exception: pass
                
            try:
                res = requests.get(f"https://search.naver.com/search.naver?where=view&query={encoded_query}", headers=headers, timeout=5)
                soup = BeautifulSoup(res.text, 'html.parser')
                for li in soup.select('.lst_view > li, .view_wrap'):
                    tit = li.select_one('.title_link')
                    desc = li.select_one('.dsc_txt')
                    user = li.select_one('.name')
                    date_tag = li.select_one('.sub_time')
                    if tit:
                        link = tit['href']
                        cat = 'cafearticle' if 'cafe.naver' in link else 'blog'
                        results.append({
                            'category': cat, 'title': tit.text, 'link': link,
                            'desc': desc.text if desc else '', 'source': user.text if user else '블로거/카페',
                            'raw_date': date_tag.text if date_tag else ''
                        })
            except Exception: pass
            return results

        def analyze_with_gemini(title, desc):
            prompt = f"""
            금융범죄 분석가로서 아래 글을 분석하여 JSON 형식으로만 답변하세요.
            - INFO: 실제 사건 보도(검거/송치), 피해자의 구체적 피해 호소/질문
            - AD: 법무법인/변호사 광고, 대출 광고, 단순 수법 교육글
            - 추출: 글에 언급된 구체적 코인명, 플랫폼명, 가명(OO팀장 등), 사이트 주소
            제목: {title}
            내용: {desc}
            출력 형식: {{"status": "INFO", "entities": ["키워드1"]}}
            """
            try:
                response = model.generate_content(prompt)
                result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                return result.get("status") == "INFO", result.get("entities", [])
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
        
        with st.spinner("웹 데이터를 스크래핑하고 AI 분석을 진행하고 있습니다..."):
            search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

            for query in search_queries:
                crawled_items = crawl_naver(query)
                for item in crawled_items:
                    ad_kws = ["법무법인", "변호사", "수임료", "승소", "고소대리", "무료상담"]
                    if any(kw in (item['title'] + item['desc']) for kw in ad_kws): continue
                    
                    dt_obj = parse_korean_date(item['raw_date'])
                    if limit_date and dt_obj < limit_date: continue
                    
                    item['datetime'] = dt_obj
                    item['date_str'] = dt_obj.strftime("%Y-%m-%d")
                    raw_results.append(item)

            unique_results = list({it['link']: it for it in raw_results}.values())
            unique_results.sort(key=lambda x: x['datetime'], reverse=True)
            
            valid_results = []
            for item in unique_results[:30]: 
                is_valid, entities = analyze_with_gemini(item['title'], item['desc'])
                if is_valid:
                    item['entities'] = entities
                    valid_results.append(item)

            grouped_results = []
            for item in valid_results:
                found_group = False
                for group in grouped_results:
                    if SequenceMatcher(None, item['title'], group[0]['title']).ratio() > 0.5:
                        group.append(item)
                        found_group = True
                        break
                if not found_group: grouped_results.append([item])

            st.divider()
            if not grouped_results:
                st.warning("조건에 맞는 데이터가 없습니다. 검색어나 기간을 조정해 보세요.")
            else:
                st.success(f"분석 완료. 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
                for group in grouped_results:
                    main = group[0]
                    with st.container():
                        st.markdown(f"#### {get_badge(main['category'])} [{main['title']}]({main['link']})")
                        col1, col2 = st.columns([8, 2])
                        with col1:
                            if main.get('entities'):
                                st.markdown("".join([f"<span class='entity-tag'># {e}</span>" for e in main['entities']]), unsafe_allow_html=True)
                        with col2:
                            st.markdown(f"<div style='text-align:right; font-size:14px; color:#86868B;'>{main['date_str']}</div>", unsafe_allow_html=True)
                        
                        st.markdown(f"<div class='result-card'><b>출처: {main['source']}</b><br><span style='color:#555;'>{main['desc']}</span></div>", unsafe_allow_html=True)
                        
                        if len(group) > 1:
                            with st.expander(f"🔗 비슷한 내용의 기사/게시글 {len(group)-1}개 더보기"):
                                for sub in group[1:]:
                                    st.markdown(f"- {get_badge(sub['category'])} [{sub['title']}]({sub['link']}) ({sub['source']} / {sub['date_str']})")

# ==========================================
# 기능 2 : 통합검색 (다중 및 커뮤니티)
# ==========================================
elif page == "통합검색":
    st.header("통합검색 대시보드")
    st.write("포털 사이트 및 주요 커뮤니티의 검색 결과를 한눈에 비교합니다.")
    
    tab1, tab2 = st.tabs(["포털 4분할 검색", "주요 커뮤니티 4분할 검색"])
    
    with tab1:
        st.subheader("🌐 네이버 / 다음 / 구글 / Bing")
        with st.form("portal_search"):
            col_in, col_btn = st.columns([8, 2])
            with col_in:
                portal_query = st.text_input("검색어", placeholder="예: 불법사금융 송치", label_visibility="collapsed", key="pq")
            with col_btn:
                portal_submit = st.form_submit_button("검색 실행")
                
        if portal_submit and portal_query:
            q = urllib.parse.quote(portal_query)
            urls = [
                f"https://m.search.naver.com/search.naver?query={q}",
                f"https://m.search.daum.net/search?w=tot&q={q}",
                f"https://www.google.com/search?q={q}&igu=1",
                f"https://www.bing.com/search?q={q}"
            ]
            st.markdown(f"""
                <div class="perfect-grid">
                    <iframe src="{urls[0]}"></iframe><iframe src="{urls[1]}"></iframe>
                    <iframe src="{urls[2]}"></iframe><iframe src="{urls[3]}"></iframe>
                </div>
            """, unsafe_allow_html=True)
            
    with tab2:
        st.subheader("🏘️ 디시인사이드 / 에펨코리아 / 루리웹 / 클리앙")
        with st.form("comm_search"):
            col_in2, col_btn2 = st.columns([8, 2])
            with col_in2:
                comm_query = st.text_input("커뮤니티 검색어", placeholder="예: 선이자", label_visibility="collapsed", key="cq")
            with col_btn2:
                comm_submit = st.form_submit_button("검색 실행")
                
        if comm_submit and comm_query:
            # 커뮤니티 사이트들은 iframe 연결을 차단하므로, 구글의 특정 사이트 검색(site:) 기능을 활용합니다.
            q_dc = urllib.parse.quote(f"site:gall.dcinside.com {comm_query}")
            q_fm = urllib.parse.quote(f"site:fmkorea.com {comm_query}")
            q_ruli = urllib.parse.quote(f"site:bbs.ruliweb.com {comm_query}")
            q_clien = urllib.parse.quote(f"site:clien.net {comm_query}")
            
            c_urls = [
                f"https://www.google.com/search?q={q_dc}&igu=1",
                f"https://www.google.com/search?q={q_fm}&igu=1",
                f"https://www.google.com/search?q={q_ruli}&igu=1",
                f"https://www.google.com/search?q={q_clien}&igu=1"
            ]
            st.markdown(f"""
                <div class="perfect-grid">
                    <iframe src="{c_urls[0]}"></iframe><iframe src="{c_urls[1]}"></iframe>
                    <iframe src="{c_urls[2]}"></iframe><iframe src="{c_urls[3]}"></iframe>
                </div>
            """, unsafe_allow_html=True)
