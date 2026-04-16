import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from difflib import SequenceMatcher

# --- UI 및 여백, 기본 메뉴 숨김 CSS 설정 (상단 여백 축소 및 아이콘 제거) ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 모니터링", layout="wide")
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 0rem;
        }
        #MainMenu {visibility: hidden;} /* 우측 상단 햄버거 메뉴 숨김 */
        header {visibility: hidden;} /* 헤더 전체 숨김 (깃허브 아이콘 포함) */
        footer {visibility: hidden;} /* 하단 Streamlit 워터마크 숨김 */
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

# --- 데이터 구조 (카테고리별 키워드) ---
CATEGORY_KEYWORDS = {
    "불법사금융": ["불법사금융", "작업대출", "대리입금", "내구제대출"],
    "리딩방": ["리딩방", "주식 리딩", "코인 리딩", "비상장주식"],
    "유사수신": ["유사수신", "원금보장", "폰지사기"]
}

# --- 사이드바 설정 ---
with st.sidebar:
    st.title("메뉴")
    selected_category = st.radio(
        "모니터링 카테고리 선택",
        options=list(CATEGORY_KEYWORDS.keys())
    )
    
    st.divider()
    st.subheader("⚙️ 검색 설정")
    st.write(f"**[{selected_category}]** 관련 기본 키워드:")
    current_keywords = st.text_area("쉼표로 구분하여 수정 가능", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=80)
    
    st.subheader("필수 검색 단어")
    mandatory_keywords = st.text_input("항상 조합해서 스크롤링할 단어", value="송치, 검거")
    
    st.divider()
    st.info("💡 AI가 법무법인 홍보, 대출 안내, 피해구제 상담 등의 광고성 글을 자동 제외합니다.")

# --- 유틸리티 함수 ---
def parse_and_format_date(date_str, category):
    """문자열 날짜를 datetime 객체로 변환하고 포맷팅 (정렬 및 출력용)"""
    KST = timezone(timedelta(hours=9))
    if category == 'news':
        try:
            # 뉴스: Thu, 16 Apr 2026 11:53:10 +0900
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt, dt.strftime("%Y-%m-%d %H:%M")
        except: 
            return datetime.now(KST), date_str
    else:
        try:
            # 블로그/카페: 20260416 (시간 데이터 없음 -> 정렬을 위해 해당 일자의 23시 59분으로 간주)
            if len(date_str) == 8:
                dt = datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]), 23, 59, 59, tzinfo=KST)
                return dt, f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return datetime.now(KST), date_str
        except: 
            return datetime.now(KST), date_str

def get_category_badge(category):
    """OS 호환성을 위해 이모지 대신 CSS 텍스트 배지 사용"""
    if category == 'news': return "<span style='color:#0058CB; font-weight:bold;'>[뉴스]</span>"
    elif category == 'blog': return "<span style='color:#03C75A; font-weight:bold;'>[블로그]</span>"
    elif category == 'cafearticle': return "<span style='color:#FF5A5A; font-weight:bold;'>[카페]</span>"
    return "<span style='color:gray; font-weight:bold;'>[기타]</span>"

def extract_source(item, category):
    """출처 정보 추출 (언론사 도메인, 블로그 작성자, 카페명)"""
    if category == 'news':
        try:
            domain = urlparse(item['originallink']).netloc
            return domain.replace("www.", "")
        except: return "뉴스"
    elif category == 'blog':
        return item.get('bloggername', '알 수 없는 블로거')
    elif category == 'cafearticle':
        return item.get('cafename', '알 수 없는 카페')
    return "알 수 없음"

def search_naver(category, query, display=15):
    """네이버 검색 API 호출"""
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": display, "sort": "date"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def is_ad_by_gemini(title, description):
    """Gemini AI를 이용한 광고 여부 판별"""
    prompt = f"""
    당신은 민생금융범죄 모니터링 요원입니다.
    
    [판별 기준]
    1. 순수 정보성 기사, 범인 검거 및 송치 뉴스, 실제 피해자의 순수 정보 공유글은 'INFO'
    2. 법무법인/변호사의 홍보 및 상담 유도글은 'AD'
    3. '불법사금융예방대출' 등 대출을 알선하거나 권유하는 글은 'AD'
    4. '피해구제 상담', '법적 대응'을 도와주겠다며 특정 오픈채팅이나 연락처로 유인하는 글은 'AD'
    
    제목: {title}
    내용: {description}
    결과값: (오직 'AD' 또는 'INFO' 만 출력)
    """
    try:
        response = model.generate_content(prompt)
        return "AD" in response.text.strip().upper()
    except:
        return False

# --- 메인 화면 ---
st.title("🔦 Fin-Light | 모니터링 대시보드")
st.markdown(f"**현재 모니터링 중인 카테고리:** `{selected_category}`")

if st.button("🚀 데이터 수집 및 분석 시작", type="primary"):
    raw_results = []
    
    base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
    mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
    
    # 기본 키워드와 필수 검색 단어 조합 생성 (예: "불법사금융 송치", "작업대출 검거")
    search_queries = []
    if mand_kws:
        for b_kw in base_kws:
            for m_kw in mand_kws:
                search_queries.append(f"{b_kw} {m_kw}")
    else:
        search_queries = base_kws

    with st.spinner("네이버 API에서 데이터를 수집하고 AI 필터링을 진행 중입니다..."):
        # 1. 데이터 수집
        for query in search_queries:
            for cat in ['news', 'blog', 'cafearticle']:
                items = search_naver(cat, query)
                for item in items:
                    title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    
                    date_key = 'pubDate' if cat == 'news' else 'postdate'
                    dt_obj, str_date = parse_and_format_date(item.get(date_key, ''), cat)
                    source_name = extract_source(item, cat)
                    
                    raw_results.append({
                        'category': cat,
                        'query': query,
                        'title': title,
                        'desc': desc,
                        'link': item['link'],
                        'datetime': dt_obj, # 정렬을 위한 객체
                        'date_str': str_date, # 출력을 위한 문자열
                        'source': source_name
                    })

        # 2. 하드 광고 필터 및 AI 필터링
        filtered_results = []
        # 중복 URL 제거를 위한 세트
        seen_links = set()
        
        for item in raw_results:
            if item['link'] in seen_links: continue
            seen_links.add(item['link'])
            
            # 1차 하드 필터 (비용 절감)
            hard_ads_keywords = ["예방대출", "피해구제 상담", "법무법인", "무료상담"]
            if any(ad_kw in item['title'] or ad_kw in item['desc'] for ad_kw in hard_ads_keywords):
                continue
                
            # 2차 AI 필터
            if not is_ad_by_gemini(item['title'], item['desc']):
                filtered_results.append(item)

        # 3. 시간순 정렬 및 클러스터링 로직 수정 (시간순 우선)
        # 전체를 먼저 시간순(최신순)으로 정렬합니다.
        filtered_results.sort(key=lambda x: x['datetime'], reverse=True)
        
        grouped_results = []
        for item in filtered_results:
            found_group = False
            for group in grouped_results:
                # 첫 번째(가장 최신) 기사와 제목 유사도가 0.5 이상이면 같은 이슈로 묶음
                if SequenceMatcher(None, item['title'], group[0]['title']).ratio() > 0.5:
                    group.append(item)
                    found_group = True
                    break
            if not found_group:
                grouped_results.append([item])
        
        # --- 결과 출력 ---
        if not grouped_results:
            st.warning("조건에 맞는 수집된 데이터가 없습니다.")
        else:
            st.success(f"시간순으로 정렬된 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
            
            for group in grouped_results:
                main_item = group[0]
                badge = get_category_badge(main_item['category'])
                
                with st.container():
                    col_badge, col_title, col_date = st.columns([1, 7, 2])
                    with col_badge:
                        st.markdown(badge, unsafe_allow_html=True)
                    with col_title:
                        st.markdown(f"**[{main_item['title']}]({main_item['link']})**")
                    with col_date:
                        st.caption(f"{main_item['date_str']}")
                    
                    # 출처 및 본문 표시
                    st.write(f"<span style='color:#555555; font-size:14px'>**출처: {main_item['source']}** | {main_item['desc']}</span>", unsafe_allow_html=True)
                    
                    if len(group) > 1:
                        with st.expander(f"🔗 비슷한 내용의 다른 출처 글 {len(group)-1}개 더보기 (시간순)"):
                            for sub_item in group[1:]:
                                sub_badge = get_category_badge(sub_item['category'])
                                st.markdown(f"{sub_badge} [{sub_item['title']}]({sub_item['link']}) | {sub_item['source']} | <span style='font-size:12px; color:gray'>{sub_item['date_str']}</span>", unsafe_allow_html=True)
                    st.divider()

else:
    st.info("좌측 메뉴에서 카테고리와 키워드를 설정한 후 [데이터 수집 및 분석 시작] 버튼을 클릭하세요.")
