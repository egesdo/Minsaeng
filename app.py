import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

# --- UI 최적화 ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 모니터링", layout="wide")
st.markdown("""
    <style>
        .block-container { padding-top: 0rem; padding-bottom: 0rem; }
        [data-testid="stSidebarNav"] { padding-top: 0rem; }
        [data-testid="stSidebar"] .st-emotion-cache-6qob1r { padding-top: 1rem; }
        #MainMenu, header, footer {visibility: hidden;}
        .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 보안 설정 ---
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("API 키 설정이 필요합니다.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 카테고리별 검색어 (정확도 향상을 위해 겹따옴표 사용) ---
CATEGORY_KEYWORDS = {
    "불법사금융": ["\"불법사금융\"", "\"작업대출\"", "\"대리입금\"", "\"내구제대출\""],
    "리딩방": ["\"리딩방\"", "\"주식 리딩\"", "\"코인 리딩\"", "\"비상장주식 사기\""],
    "유사수신": ["\"유사수신\"", "\"폰지사기\"", "\"다단계 사기\""]
}

with st.sidebar:
    st.markdown("<h2 style='margin-top:0;'>🔦 Fin-Light</h2>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리 선택", options=list(CATEGORY_KEYWORDS.keys()))
    
    st.divider()
    st.subheader("⚙️ 모니터링 설정")
    st.caption("정확한 검색을 위해 따옴표(\") 유지를 권장합니다.")
    current_keywords = st.text_area("검색 키워드", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
    mandatory_keywords = st.text_input("필수 포함 단어 (빈칸 가능)", value="송치, 검거")

def get_badge(category):
    if category == 'news': return "<span style='color:#0058CB; font-weight:bold;'>[뉴스]</span>"
    elif category == 'blog': return "<span style='color:#03C75A; font-weight:bold;'>[블로그]</span>"
    elif category == 'cafearticle': return "<span style='color:#FF5A5A; font-weight:bold;'>[카페]</span>"
    return "[기타]"

def search_naver(category, query, display=50):
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": display, "sort": "sim"} # 유사도순으로 변경 (최신순은 가비지가 너무 많음)
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', []) if response.status_code == 200 else []

def is_hard_ad(title, desc):
    """1차 텍스트 필터: 절대 포함되면 안 되는 광고/무관 단어 차단"""
    ad_keywords = [
        "법무법인", "변호사", "법률사무소", "수임료", "승소", "고소대리", "오픈채팅", "무료상담", 
        "택배", "기사님", "월매출", "야간", "고정", "대리운전", "탁송", "판매", "팝니다", "엘몰", "신발",
        "챌린지", "신문읽기", "4차 산업혁명"
    ]
    text = title + desc
    for kw in ad_keywords:
        if kw in text: return True
    return False

def classify_by_gemini(title, desc, category_name):
    """2차 AI 필터: 실제 사건보도, 검거소식, 피해자 질문만 남김"""
    prompt = f"""
    이 글이 '{category_name}' 범죄 사건과 관련된 보도이거나, 피해자의 질문/호소 글인지 판별하라.
    광고나 홍보, 변호사 글, 타 범죄, 일반 주식/가상화폐 뉴스, 단순 일상 글이면 무조건 'AD'로 답하라.
    관련된 핵심 정보면 'INFO'로 답하라.
    
    제목: {title}
    내용: {desc}
    답변(AD 또는 INFO):"""
    try:
        res = model.generate_content(prompt)
        return "AD" not in res.text.strip().upper()
    except Exception as e:
        # API 오류 시 기본적으로 버림(False) 처리하여 쓰레기 데이터 노출 방지
        return False

# --- 메인 로직 ---
st.markdown(f"<h3 style='margin-bottom:0;'>💡 Fin-Light | {selected_category} 집중 모니터링</h3>", unsafe_allow_html=True)

if st.button("🚀 데이터 수집 및 정밀 분석 시작"):
    raw_results = []
    base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
    mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
    
    with st.spinner("가비지 데이터를 걸러내고 핵심 정보만 추출 중입니다..."):
        
        # 검색 쿼리 생성 (필수 단어가 있으면 조합)
        search_queries = []
        if mand_kws:
            for b_kw in base_kws:
                for m_kw in mand_kws:
                    search_queries.append(f"{b_kw} {m_kw}")
        else:
            search_queries = base_kws

        # 데이터 수집
        for query in search_queries:
            for cat in ['news', 'blog', 'cafearticle']:
                items = search_naver(cat, query)
                for item in items:
                    title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    
                    # 1차 초강력 하드 필터 실행 (광고 및 쓰레기 데이터 즉시 삭제)
                    if is_hard_ad(title, desc): continue
                    
                    raw_results.append({
                        'category': cat, 'title': title, 'desc': desc, 'link': item['link'],
                        'source': urlparse(item['link']).netloc.replace("www.", "") if cat=='news' else item.get('bloggername' if cat=='blog' else 'cafename', '알 수 없음')
                    })

        # 중복 제거
        unique_results = list({it['link']: it for it in raw_results}.values())

        # 2차 AI 필터링 진행
        final_display = []
        for item in unique_results:
            if classify_by_gemini(item['title'], item['desc'], selected_category):
                final_display.append(item)

        if not final_display:
            st.error("조건에 맞는 유효한 데이터가 없습니다. 필수 포함 단어(송치, 검거)를 지우고 다시 검색해보세요.")
        else:
            st.success(f"필터링 완료. {len(final_display)}건의 유효한 정보가 발견되었습니다.")
            for item in final_display[:30]:
                with st.container():
                    c1, c2 = st.columns([1, 9])
                    c1.markdown(get_badge(item['category']), unsafe_allow_html=True)
                    c2.markdown(f"**[{item['title']}]({item['link']})**")
                    st.markdown(f"<div style='font-size:13px; color:#444; background-color:#F0F2F6; padding:5px; border-radius:5px;'><b>출처: {item['source']}</b> | {item['desc']}</div>", unsafe_allow_html=True)
                    st.divider()
