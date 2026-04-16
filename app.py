import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import json
from difflib import SequenceMatcher

# --- 기본 설정 ---
st.set_page_config(page_title="Fin-Light | 통합 대시보드", layout="wide", initial_sidebar_state="expanded")

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "AI"

# --- 안전한 Apple 스타일 CSS ---
base_css = """
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
    html, body, .stApp {
        font-family: 'Pretendard Variable', -apple-system, sans-serif !important;
        background-color: #FBFBFD !important;
    }
    header[data-testid="stHeader"], footer, .stDeployButton, #MainMenu { display: none !important; } 
    
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E5EA !important;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
        border-radius: 10px !important;
        border: 1px solid #D2D2D7 !important;
    }
    .stButton > button {
        border-radius: 980px !important; 
        background-color: #0071E3 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
    }
    .stButton > button:hover { background-color: #0077ED !important; transform: scale(0.98); }
    
    .apple-title-box {
        background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%);
        border: 1px solid #E5E5EA;
        border-radius: 16px;
        padding: 18px 15px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
    }
    .apple-title-text { font-size: 22px; font-weight: 800; color: #1D1D1F; letter-spacing: -0.5px; }
    .apple-subtitle-text { font-size: 11px; color: #86868B; margin-top: 4px; }
    
    .perfect-grid { display: flex; flex-wrap: wrap; width: 100%; height: 100vh; }
    .perfect-grid iframe { width: 50%; height: 50vh; border: 1px solid #E5E5EA; border-top:none; border-left:none; box-sizing: border-box; }
    .entity-tag { background-color: #E8F0FE; color: #1967D2; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-right: 5px; margin-bottom: 5px; display: inline-block; }
"""

# 💡 문제 해결 핵심: 모드별 패딩(여백) 명확한 분리 적용
if st.session_state.view_mode == "MULTI":
    layout_css = ".block-container { padding: 0rem !important; max-width: 100% !important; }"
else:
    # 좌우 여백을 5% 주어 왼쪽으로 쏠리는 현상을 완벽히 차단
    layout_css = ".block-container { padding: 3rem 5% !important; max-width: 1300px !important; margin: 0 auto !important; }"

st.markdown(f"<style>{base_css} {layout_css}</style>", unsafe_allow_html=True)

# --- API 설정 ---
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("API 키 설정이 필요합니다. Streamlit Cloud의 Secrets 설정을 확인해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "작업대출 후기", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 날짜 파싱 및 유사도 함수 ---
def parse_date(date_str, category):
    KST = timezone(timedelta(hours=9))
    dt = datetime.now(KST)
    if category == 'news':
        try: dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except: pass
        return dt, dt.strftime("%Y-%m-%d %H:%M")
    else:
        try:
            if len(date_str) == 8:
                dt = datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]), 23, 59, 59, tzinfo=KST)
        except: pass
        return dt, dt.strftime("%Y-%m-%d")

def is_similar(a, b, threshold=0.5):
    return SequenceMatcher(None, a, b).ratio() > threshold

# --- 사이드바 ---
with st.sidebar:
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text"><span>🔦</span> Fin-Light</div>
            <div class="apple-subtitle-text">민생금융범죄 모니터링 시스템</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🤖 AI 정밀 모니터링</h4>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리", options=list(CATEGORY_KEYWORDS.keys()), label_visibility="collapsed")
    current_keywords = st.text_area("AI 검색어", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
    mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
    
    date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
    
    if st.button("AI 분석 모드 열기", key="btn_ai"):
        st.session_state.view_mode = "AI"
        st.rerun()

    st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🔍 통합 다중 검색 (4분할)</h4>", unsafe_allow_html=True)
    
    with st.form(key="multi_search_form"):
        multi_query = st.text_input("검색어 입력 후 엔터", placeholder="예: 선이자")
        submit_btn = st.form_submit_button("검색")
        
    if submit_btn and multi_query:
        st.session_state.multi_query = multi_query
        st.session_state.view_mode = "MULTI"
        st.rerun()

# --- [VIEW 1] 4분할 다중 검색 모드 ---
if st.session_state.view_mode == "MULTI" and "multi_query" in st.session_state:
    q = quote(st.session_state.multi_query)
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

# --- [VIEW 2] AI 정밀 모니터링 모드 ---
else:
    def search_naver(category, query, display=40):
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
        params = {"query": query, "display": display, "sort": "date"}
        response = requests.get(url, headers=headers, params=params)
        return response.json().get('items', []) if response.status_code == 200 else []

    def is_hard_ad(title, desc):
        ad_keywords = ["법무법인", "변호사", "법률사무소", "수임료", "승소", "고소대리", "상담문의", "해결사", "무료법률상담"]
        return any(kw in (title + desc) for kw in ad_keywords)

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
        elif category == 'cafearticle': return "<span style='color:#FF3B30; font-weight:700;'>[카페]</span>"
        return "<span style='color:#8E8E93; font-weight:700;'>[기타]</span>"

    st.markdown(f"<h2 style='color:#1D1D1F; font-weight:800; letter-spacing:-1px;'>🤖 {selected_category} AI 정밀 분석 모드</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#86868B; margin-bottom:20px;'>유사한 기사는 묶어서 보여주며, 지정된 기간의 데이터만 필터링합니다.</p>", unsafe_allow_html=True)
    
    if st.button("🚀 정밀 분석 실행", key="run_ai_btn"):
        # 기간 제한 설정
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
                        
                        if is_hard_ad(title, desc): continue
                        
                        dt_obj, date_str = parse_date(item.get('pubDate' if cat == 'news' else 'postdate', ''), cat)
                        
                        if limit_date and dt_obj < limit_date:
                            continue

                        raw_results.append({
                            'category': cat, 'title': title, 'desc': desc, 'link': item['link'],
                            'source': urlparse(item['link']).netloc.replace("www.", "") if cat=='news' else item.get('bloggername' if cat=='blog' else 'cafename', '알 수 없음'),
                            'date_str': date_str,
                            'datetime': dt_obj
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
                    if is_similar(item['title'], group[0]['title']):
                        group.append(item)
                        found_group = True
                        break
                if not found_group:
                    grouped_results.append([item])

            if not grouped_results:
                st.warning("설정된 기간 내에 유효한 데이터가 없습니다.")
            else:
                st.success(f"분석 완료. 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
                for group in grouped_results:
                    main_item = group[0]
                    with st.container():
                        st.markdown(f"{get_badge(main_item['category'])} <a href='{main_item['link']}' target='_blank' style='text-decoration:none; color:#1D1D1F; font-size:16px; font-weight:600;'>{main_item['title']}</a> <span style='float:right; font-size:12px; color:#86868B;'>{main_item['date_str']}</span>", unsafe_allow_html=True)
                        
                        if main_item.get('entities'):
                            entity_html = "".join([f"<span class='entity-tag'>{e}</span>" for e in main_item['entities']])
                            st.markdown(entity_html, unsafe_allow_html=True)
                        
                        st.markdown(f"<div style='font-size:13px; color:#444; background-color:#FFFFFF; border:1px solid #E5E5EA; padding:10px 12px; border-radius:10px; margin-top:6px; box-shadow:0 1px 3px rgba(0,0,0,0.02);'><b>출처: {main_item['source']}</b><br><span style='color:#666;'>{main_item['desc']}</span></div>", unsafe_allow_html=True)
                        
                        if len(group) > 1:
                            with st.expander(f"🔗 비슷한 내용의 기사/글 {len(group)-1}개 더보기"):
                                for sub_item in group[1:]:
                                    st.markdown(f"{get_badge(sub_item['category'])} [{sub_item['title']}]({sub_item['link']}) <span style='font-size:11px; color:#86868B;'>| {sub_item['source']} | {sub_item['date_str']}</span>", unsafe_allow_html=True)
                        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
