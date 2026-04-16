import streamlit as st
import streamlit.components.v1 as components
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import json
from difflib import SequenceMatcher

# --- 기본 설정 ---
st.set_page_config(page_title="Fin-Light | 모니터링 시스템", layout="wide", initial_sidebar_state="expanded")

# --- 전역 CSS (애플 스타일 공통 적용, 레이아웃은 건드리지 않음) ---
global_css = """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp { font-family: 'Pretendard Variable', -apple-system, sans-serif !important; background-color: #FBFBFD !important; }
    
    /* 헤더(깃허브), 푸터(스트림릿) 로고 제거 */
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E5E5EA !important; }
    
    /* 입력창 및 버튼 디자인 */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div { border-radius: 10px !important; border: 1px solid #D2D2D7 !important; }
    .stButton > button { border-radius: 980px !important; background-color: #0071E3 !important; color: #FFFFFF !important; border: none !important; font-weight: 600 !important; width: 100%; }
    .stButton > button:hover { background-color: #0077ED !important; transform: scale(0.98); }
    
    /* 타이틀 박스 */
    .apple-title-box { background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%); border: 1px solid #E5E5EA; border-radius: 16px; padding: 18px 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03); }
    .apple-title-text { font-size: 22px; font-weight: 800; color: #1D1D1F; letter-spacing: -0.5px; }
    .apple-subtitle-text { font-size: 11px; color: #86868B; margin-top: 4px; }
    
    /* 엔티티 태그 */
    .entity-tag { background-color: #E8F0FE; color: #1967D2; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-right: 5px; margin-bottom: 5px; display: inline-block; }
    </style>
"""
st.markdown(global_css, unsafe_allow_html=True)

# --- API 설정 ---
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

# --- 사이드바 및 페이지 라우터 ---
with st.sidebar:
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text"><span>🔦</span> Fin-Light</div>
            <div class="apple-subtitle-text">민생금융범죄 모니터링 시스템</div>
        </div>
    """, unsafe_allow_html=True)
    
    # 완전히 분리된 메뉴 이동 버튼
    page = st.radio("메뉴 이동", ["🤖 AI 정밀 분석", "🔍 4분할 다중 검색"])
    st.divider()

# ==========================================
# PAGE 1 : AI 정밀 분석 모드
# ==========================================
if page == "🤖 AI 정밀 분석":
    # 스트림릿 기본 여백을 유지하여 화면 찌그러짐 원천 차단
    st.markdown("<style>.block-container { padding-top: 2rem !important; }</style>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("<h4 style='font-size:14px;'>⚙️ AI 분석 설정</h4>", unsafe_allow_html=True)
        selected_category = st.radio("카테고리", options=list(CATEGORY_KEYWORDS.keys()), label_visibility="collapsed")
        current_keywords = st.text_area("검색어", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
        mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
        date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
        run_btn = st.button("🚀 정밀 분석 실행")

    st.markdown(f"<h2 style='color:#1D1D1F; font-weight:800;'>🤖 {selected_category} AI 정밀 분석</h2>", unsafe_allow_html=True)
    st.caption("AI가 유사한 기사를 자동으로 묶어주며, 광고성 글을 배제합니다.")

    if run_btn:
        def parse_date(date_str, category):
            KST = timezone(timedelta(hours=9))
            dt = datetime.now(KST)
            if category == 'news':
                try: dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                except: pass
                return dt, dt.strftime("%Y-%m-%d %H:%M")
            else:
                try:
                    if len(date_str) == 8: dt = datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]), 23, 59, 59, tzinfo=KST)
                except: pass
                return dt, dt.strftime("%Y-%m-%d")

        def search_naver(category, query, display=40):
            url = f"https://openapi.naver.com/v1/search/{category}.json"
            headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
            params = {"query": query, "display": display, "sort": "date"}
            response = requests.get(url, headers=headers, params=params)
            return response.json().get('items', []) if response.status_code == 200 else []

        def analyze_with_gemini(title, desc):
            prompt = f"""
            금융범죄 분석가로서 아래 글을 분석하여 JSON 형식으로만 답변하세요.
            - INFO: 실제 사건 보도(검거/송치), 피해자의 구체적 피해 호소/질문
            - AD: 법무법인 광고, 일반적 수법 교육글
            - 추출: 글에 언급된 구체적 코인명, 플랫폼명, 가명(OO팀장 등), 사이트 주소
            제목: {title}
            내용: {desc}
            출력 형식: {{"status": "INFO", "entities": ["키워드1"]}}
            """
            try:
                response = model.generate_content(prompt)
                result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
                return result.get("status") == "INFO", result.get("entities", [])
            except:
                return True, [] 

        def get_badge(category):
            if category == 'news': return "<span style='color:#0071E3; font-weight:700;'>[뉴스]</span>"
            elif category == 'blog': return "<span style='color:#34C759; font-weight:700;'>[블로그]</span>"
            return "<span style='color:#FF3B30; font-weight:700;'>[카페]</span>"

        now_kst = datetime.now(timezone(timedelta(hours=9)))
        if date_filter == "최근 1개월": limit_date = now_kst - timedelta(days=30)
        elif date_filter == "최근 3개월": limit_date = now_kst - timedelta(days=90)
        elif date_filter == "최근 1년": limit_date = now_kst - timedelta(days=365)
        else: limit_date = None

        raw_results = []
        base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
        mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
        
        with st.spinner(f"데이터를 수집하고 분석 중입니다... ({date_filter} 기준)"):
            search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

            for query in search_queries:
                for cat in ['news', 'blog', 'cafearticle']:
                    items = search_naver(cat, query)
                    for item in items:
                        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                        desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                        
                        ad_kws = ["법무법인", "변호사", "법률사무소", "수임료", "승소", "고소대리", "상담문의", "해결사"]
                        if any(kw in (title + desc) for kw in ad_kws): continue
                        
                        dt_obj, date_str = parse_date(item.get('pubDate' if cat == 'news' else 'postdate', ''), cat)
                        if limit_date and dt_obj < limit_date: continue

                        raw_results.append({
                            'category': cat, 'title': title, 'desc': desc, 'link': item['link'],
                            'source': urlparse(item['link']).netloc.replace("www.", "") if cat=='news' else item.get('bloggername' if cat=='blog' else 'cafename', '알 수 없음'),
                            'date_str': date_str, 'datetime': dt_obj
                        })

            unique_results = list({it['link']: it for it in raw_results}.values())
            unique_results.sort(key=lambda x: x['datetime'], reverse=True)
            
            valid_results = []
            for item in unique_results[:40]: 
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

            if not grouped_results:
                st.warning("설정된 기간 내에 유효한 데이터가 없습니다.")
            else:
                st.success(f"분석 완료. 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
                for group in grouped_results:
                    main = group[0]
                    with st.container():
                        st.markdown(f"{get_badge(main['category'])} <a href='{main['link']}' target='_blank' style='text-decoration:none; color:#1D1D1F; font-size:16px; font-weight:600;'>{main['title']}</a> <span style='float:right; font-size:12px; color:#86868B;'>{main['date_str']}</span>", unsafe_allow_html=True)
                        if main.get('entities'):
                            st.markdown("".join([f"<span class='entity-tag'>{e}</span>" for e in main['entities']]), unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:13px; color:#444; background-color:#FFFFFF; border:1px solid #E5E5EA; padding:10px 12px; border-radius:10px; margin-top:6px;'><b>출처: {main['source']}</b><br><span style='color:#666;'>{main['desc']}</span></div>", unsafe_allow_html=True)
                        
                        if len(group) > 1:
                            with st.expander(f"🔗 비슷한 내용의 기사/글 {len(group)-1}개 더보기"):
                                for sub in group[1:]:
                                    st.markdown(f"{get_badge(sub['category'])} [{sub['title']}]({sub['link']}) <span style='font-size:11px; color:#86868B;'>| {sub['source']} | {sub['date_str']}</span>", unsafe_allow_html=True)
                        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

# ==========================================
# PAGE 2 : 4분할 다중 검색 모드
# ==========================================
elif page == "🔍 4분할 다중 검색":
    # 이 페이지에서만 강제로 화면을 100% 채우고 여백을 없애는 CSS 적용
    st.markdown("""
        <style>
        .block-container { padding: 0rem !important; margin: 0rem !important; max-width: 100% !important; }
        .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; height: 100vh; }
        .perfect-grid iframe { width: 50%; height: 50vh; border: 1px solid #E5E5EA; border-top:none; border-left:none; box-sizing: border-box; }
        </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("<h4 style='font-size:14px;'>🔍 검색어 입력</h4>", unsafe_allow_html=True)
        multi_query = st.text_input("검색어", placeholder="예: 선이자", label_visibility="collapsed")
        search_btn = st.button("🚀 4분할 검색 실행")
        
    if search_btn and multi_query:
        q = quote(multi_query)
        urls = [
            f"https://m.search.naver.com/search.naver?query={q}",
            f"https://www.google.com/search?q={q}&igu=1",
            f"https://m.search.daum.net/search?w=tot&q={q}",
            f"https://www.bing.com/search?q={q}"
        ]
        st.markdown(f"""
            <div class="perfect-grid">
                <iframe src="{urls[0]}"></iframe>
                <iframe src="{urls[1]}"></iframe>
                <iframe src="{urls[2]}"></iframe>
                <iframe src="{urls[3]}"></iframe>
            </div>
        """, unsafe_allow_html=True)
    elif not multi_query:
        # 검색어가 없을 때 빈 화면 안내
        st.markdown("<div style='padding:50px; text-align:center; color:#86868B;'>좌측 사이드바에서 검색어를 입력하고 실행 버튼을 눌러주세요.</div>", unsafe_allow_html=True)
