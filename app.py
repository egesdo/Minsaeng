import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from difflib import SequenceMatcher

# --- UI 최적화 및 여백 제거 CSS ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 모니터링", layout="wide")
st.markdown("""
    <style>
        /* 메인 상단 여백 제거 */
        .block-container { padding-top: 0rem; padding-bottom: 0rem; }
        /* 사이드바 상단 여백 제거 */
        [data-testid="stSidebarNav"] { padding-top: 0rem; }
        [data-testid="stSidebar"] .st-emotion-cache-6qob1r { padding-top: 1rem; }
        /* 기본 메뉴 숨김 */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        /* 검색 버튼 스타일 */
        .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 보안 설정 ---
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("API 키 설정이 필요합니다. Streamlit Cloud의 Secrets 설정을 확인해주세요.")
    st.stop()

# --- Gemini 설정 ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 타겟 카페 설정 ---
TARGET_CAFES = {
    "불법사금융": "sachaesingo", # 불법사금융 피해자 모임
    "리딩방": "notouch7",      # 유사수신 행위 등 투자사기 피해자 모임
    "유사수신": "notouch7"
}

CATEGORY_KEYWORDS = {
    "불법사금융": ["불법사금융", "작업대출", "대리입금", "내구제대출"],
    "리딩방": ["리딩방", "주식 리딩", "코인 리딩", "비상장주식"],
    "유사수신": ["유사수신", "원금보장", "폰지사기", "피라미드 사기"]
}

# --- 사이드바 ---
with st.sidebar:
    st.markdown("<h2 style='margin-top:0;'>🔦 Fin-Light</h2>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리 선택", options=list(CATEGORY_KEYWORDS.keys()))
    
    st.divider()
    st.subheader("⚙️ 모니터링 설정")
    current_keywords = st.text_area("검색 키워드", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
    mandatory_keywords = st.text_input("필수 조합 단어", value="송치, 검거")
    
    st.caption(f"💡 현재 카테고리는 카페 **'{TARGET_CAFES[selected_category]}'** 글을 우선 수집합니다.")

# --- 함수 정의 ---
def parse_date(date_str, category):
    KST = timezone(timedelta(hours=9))
    if category == 'news':
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt, dt.strftime("%Y-%m-%d %H:%M")
        except: return datetime.now(KST), date_str
    else:
        try:
            if len(date_str) == 8:
                dt = datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]), 23, 59, 59, tzinfo=KST)
                return dt, f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return datetime.now(KST), date_str
        except: return datetime.now(KST), date_str

def get_badge(category):
    if category == 'news': return "<span style='color:#0058CB; font-weight:bold;'>[뉴스]</span>"
    elif category == 'blog': return "<span style='color:#03C75A; font-weight:bold;'>[블로그]</span>"
    elif category == 'cafearticle': return "<span style='color:#FF5A5A; font-weight:bold;'>[카페]</span>"
    return "[기타]"

def extract_source(item, category):
    if category == 'news':
        try: return urlparse(item['originallink']).netloc.replace("www.", "")
        except: return "뉴스"
    return item.get('bloggername' if category == 'blog' else 'cafename', '알 수 없음')

def search_naver(category, query, display=30):
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": display, "sort": "date"}
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', []) if response.status_code == 200 else []

def classify_content(title, desc, category_name):
    """Gemini를 이용한 정밀 분류: 대응 방법 안내(AD) vs 사건보도/피해자질문(INFO)"""
    prompt = f"""
    당신은 금융범죄 수사 모니터링 전문가입니다. 다음 글이 '{category_name}' 범죄와 직접 관련이 있는지, 그리고 광고성인지 판별하세요.

    [제외 대상 - 'AD']
    1. 법무법인, 변호사가 작성한 '대응 방법 안내', '피해 구제 절차' 홍보글.
    2. '불법사금융 예방 대출' 등 대출 광고.
    3. 해당 범죄({category_name})와 상관없는 일반 강력 범죄(살인, 절도 등) 뉴스.

    [포함 대상 - 'INFO']
    1. {category_name} 관련 범인 검거, 검찰 송치 뉴스.
    2. 피해자가 자신의 상황을 설명하며 "어떻게 해야 하나요?"라고 '질문'하는 글.
    3. 실제 피해 수법을 공유하는 글.

    제목: {title}
    내용: {desc}
    결과(AD/INFO):"""
    
    try:
        response = model.generate_content(prompt)
        return "AD" not in response.text.strip().upper()
    except: return True

# --- 메인 로직 ---
st.markdown("<h3 style='margin-bottom:0;'>💡 Fin-Light | 모니터링 대시보드</h3>", unsafe_allow_html=True)

if st.button("🚀 모니터링 시작"):
    raw_results = []
    base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
    mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
    
    with st.spinner("최신 데이터를 분석 중입니다..."):
        # 1. 특정 카페 우선 수집 및 키워드 조합 검색
        target_cafe_id = TARGET_CAFES[selected_category]
        
        for b_kw in base_kws:
            # 타겟 카페 글 수집 (검색어에 카페 ID 조합)
            cafe_items = search_naver('cafearticle', f"cafe.naver.com/{target_cafe_id} {b_kw}")
            
            # 뉴스 및 블로그 (송치/검거 조합)
            other_items = []
            for m_kw in mand_kws:
                other_items.extend(search_naver('news', f"{b_kw} {m_kw}"))
                other_items.extend(search_naver('blog', f"{b_kw} {m_kw}"))
            
            for item in (cafe_items + other_items):
                cat = 'news' if 'originallink' in item else ('blog' if 'bloggername' in item else 'cafearticle')
                
                # 링크 분석을 통한 특정 카페글 강제 포함 여부 확인
                is_target_cafe = target_cafe_id in item['link']
                
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                
                dt_obj, str_date = parse_date(item.get('pubDate' if cat == 'news' else 'postdate', ''), cat)
                
                raw_results.append({
                    'category': cat,
                    'title': title,
                    'desc': desc,
                    'link': item['link'],
                    'datetime': dt_obj,
                    'date_str': str_date,
                    'source': extract_source(item, cat),
                    'is_target_cafe': is_target_cafe
                })

        # 2. 중복 제거 및 정렬
        unique_results = {it['link']: it for it in raw_results}.values()
        sorted_results = sorted(unique_results, key=lambda x: x['datetime'], reverse=True)

        # 3. AI 정밀 필터링 (타겟 카페 글은 필터링 완화, 뉴스는 엄격히)
        final_display = []
        for item in sorted_results:
            # 타겟 카페 글은 웬만하면 포함, 그 외는 AI 분류
            if item['is_target_cafe'] or classify_content(item['title'], item['desc'], selected_category):
                final_display.append(item)

        # 4. 출력
        if not final_display:
            st.warning("분석 결과 표시할 내용이 없습니다.")
        else:
            for item in final_display[:40]: # 상위 40개
                with st.container():
                    c1, c2, c3 = st.columns([1, 7, 2])
                    c1.markdown(get_badge(item['category']), unsafe_allow_html=True)
                    c2.markdown(f"**[{item['title']}]({item['link']})**")
                    c3.caption(item['date_str'])
                    
                    # 출처 강조 및 본문
                    source_style = "background-color:#F0F2F6; padding:2px 5px; border-radius:3px; font-weight:bold;"
                    st.markdown(f"<div style='font-size:13px; color:#444;'><span style='{source_style}'>{item['source']}</span> {item['desc']}</div>", unsafe_allow_html=True)
                    st.divider()
