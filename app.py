import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import json

# --- UI 및 여백 설정 ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 정밀 모니터링", layout="wide")
st.markdown("""
    <style>
        .block-container { padding-top: 0.5rem; padding-bottom: 0rem; }
        [data-testid="stSidebarNav"] { padding-top: 0rem; }
        #MainMenu, header, footer {visibility: hidden;}
        .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
        .entity-tag { background-color: #e1e4e8; color: #0366d6; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-right: 4px; }
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

# --- 지능형 검색 키워드 설정 (피해 사례 분석 기반) ---
CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "작업대출 후기", "대출중개사이트 사기", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "보상절차 안내 사기", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "해외 거래소 사기", "다단계 코인"]
}

with st.sidebar:
    st.markdown("<h2 style='margin-top:0;'>🔦 Fin-Light</h2>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리 선택", options=list(CATEGORY_KEYWORDS.keys()))
    
    st.divider()
    st.subheader("⚙️ 검색 키워드 (지능형 자동 설정)")
    current_keywords = st.text_area("검색어 (수정 가능)", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=100)
    mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")

def get_badge(category):
    if category == 'news': return "<span style='color:#0058CB;'>[뉴스]</span>"
    elif category == 'blog': return "<span style='color:#03C75A;'>[블로그]</span>"
    elif category == 'cafearticle': return "<span style='color:#FF5A5A;'>[카페]</span>"
    return "[기타]"

def is_hard_ad(title, desc):
    """법무법인 및 일반 광고성 글 초강력 필터링"""
    ad_keywords = [
        "법무법인", "변호사", "법률사무소", "수임료", "승소", "고소대리", "상담문의", "해결사", 
        "전문가 조력", "대응방법 안내", "성공사례", "판결문 분석", "무료법률상담", "오픈채팅",
        "리딩방 사칭", "로맨스스캠 주의", "신종수법 안내" # 정보 공유를 가장한 일반적 공지글 제외
    ]
    text = title + desc
    return any(kw in text for kw in ad_keywords)

def analyze_with_gemini(title, desc, category_name):
    """AI를 통한 정밀 분류 및 핵심 키워드(코인명, 인물 등) 추출"""
    prompt = f"""
    당신은 금융범죄 전문 분석가입니다. 아래 글을 분석하여 JSON 형식으로만 답변하세요.
    
    [판별 기준]
    - 유효(INFO): 실제 사건 보도(검거/송치), 피해자가 구체적으로 올린 피해 호소 및 질문.
    - 제외(AD): 법무법인 광고, 일반적인 범죄 수법 교육/공지글, 단순히 '사칭/스캠 주의'라고만 언급된 유용성 낮은 글.
    
    [추출]
    - 글에서 언급된 구체적인 '코인명', '플랫폼명', '가명(OO팀장 등)', '사이트 주소'를 리스트로 추출하세요.
    
    제목: {title}
    내용: {desc}
    
    출력 형식: {{"status": "INFO" 또는 "AD", "entities": ["키워드1", "키워드2"]}}
    """
    try:
        response = model.generate_content(prompt)
        result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
        return result.get("status") == "INFO", result.get("entities", [])
    except:
        return True, [] # 에러 시 데이터 보존을 위해 통과

def search_naver(category, query, display=40):
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": display, "sort": "date"}
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', []) if response.status_code == 200 else []

# --- 메인 실행 ---
st.markdown(f"### 💡 {selected_category} 정밀 모니터링")

if st.button("🚀 정밀 분석 시작"):
    raw_results = []
    base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
    mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
    
    with st.spinner("가비지 데이터를 걸러내고 핵심 개체를 추출 중입니다..."):
        # 검색 쿼리 실행
        search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

        for query in search_queries:
            for cat in ['news', 'blog', 'cafearticle']:
                items = search_naver(cat, query)
                for item in items:
                    title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    
                    if is_hard_ad(title, desc): continue
                    
                    date_key = 'pubDate' if cat == 'news' else 'postdate'
                    raw_date = item.get(date_key, '')
                    
                    # 날짜 가독성 처리
                    try:
                        if cat == 'news':
                            dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %z")
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        else:
                            date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                    except: date_str = raw_date

                    raw_results.append({
                        'category': cat, 'title': title, 'desc': desc, 'link': item['link'],
                        'source': urlparse(item['link']).netloc.replace("www.", "") if cat=='news' else item.get('bloggername' if cat=='blog' else 'cafename', '알 수 없음'),
                        'date_str': date_str
                    })

        # 중복 제거 및 AI 분석
        unique_results = list({it['link']: it for it in raw_results}.values())
        final_display = []
        for item in unique_results[:50]: # 성능을 위해 상위 50건 분석
            is_valid, entities = analyze_with_gemini(item['title'], item['desc'], selected_category)
            if is_valid:
                item['entities'] = entities
                final_display.append(item)

        # 결과 출력
        if not final_display:
            st.warning("유효한 데이터가 없습니다. 검색 설정을 조정해 보세요.")
        else:
            for item in final_display:
                with st.container():
                    col_main, col_date = st.columns([8, 2])
                    with col_main:
                        badge = get_badge(item['category'])
                        st.markdown(f"{badge} **[{item['title']}]({item['link']})**", unsafe_allow_html=True)
                    with col_date:
                        st.markdown(f"<p style='text-align:right; font-size:12px; color:gray;'>{item['date_str']}</p>", unsafe_allow_html=True)
                    
                    # 추출된 엔티티(코인명, 가명 등) 표시
                    if item.get('entities'):
                        entity_html = "".join([f"<span class='entity-tag'>{e}</span>" for e in item['entities']])
                        st.markdown(entity_html, unsafe_allow_html=True)
                    
                    st.markdown(f"<div style='font-size:13px; color:#444; background-color:#F8F9FA; padding:8px; border-radius:5px; margin-top:5px;'><b>{item['source']}</b> | {item['desc']}</div>", unsafe_allow_html=True)
                    st.divider()
