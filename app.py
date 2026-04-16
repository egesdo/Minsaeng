import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime
from difflib import SequenceMatcher

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

# --- 페이지 설정 ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 모니터링", layout="wide")
st.title("🔦 Fin-Light | 민생금융범죄 모니터링 시스템")
st.caption("불법사금융, 유사수신, 리딩방 관련 온라인 최신 정보를 통합 모니터링합니다.")

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("⚙️ 모니터링 설정")
    
    st.subheader("1. 기본 키워드")
    default_keywords = "불법사금융, 리딩방 사기, 원금보장 투자, 작업대출, 비상장주식 리딩"
    user_keywords = st.text_area("모니터링 대상 (쉼표로 구분)", value=default_keywords, height=80)
    keywords_list = [k.strip() for k in user_keywords.split(",") if k.strip()]
    
    st.subheader("2. 필수 포함 문구 (택 1 이상 포함)")
    default_mandatory = "송치, 검거"
    user_mandatory = st.text_input("반드시 포함할 단어 (쉼표로 구분)", value=default_mandatory)
    mandatory_list = [m.strip() for m in user_mandatory.split(",") if m.strip()]
    
    st.divider()
    st.info("💡 AI가 법무법인 홍보, 예방대출 안내, 피해구제/대응 상담 유도 글을 자동으로 제외합니다.")

# --- 유틸리티 함수 ---
def format_date(date_str, category):
    """네이버 API 날짜 형식을 보기 좋게 변환"""
    if category == 'news':
        try: # 뉴스: Thu, 16 Apr 2026 11:53:10 +0900
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
            return dt.strftime("%Y-%m-%d %H:%M")
        except: return date_str
    else:
        try: # 블로그/카페: 20260416 (시간 제공 안됨)
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        except: return date_str

def get_category_badge(category):
    """카테고리별 색상 및 라벨 지정"""
    if category == 'news': return "🟦 **[뉴스]**"
    elif category == 'blog': return "🟩 **[블로그]**"
    elif category == 'cafearticle': return "🟧 **[카페]**"
    return "⬛ [기타]"

def is_similar(a, b, threshold=0.5):
    """제목 간의 유사도 측정 (0.5 이상이면 비슷한 기사로 간주)"""
    return SequenceMatcher(None, a, b).ratio() > threshold

def search_naver(category, query, display=15):
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    params = {"query": query, "display": display, "sort": "date"} # 최신순 정렬
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def is_ad_by_gemini(title, description):
    prompt = f"""
    당신은 민생금융범죄 모니터링 요원입니다. 아래 글의 제목과 내용을 분석하세요.
    
    [판별 기준]
    1. 순수 정보성 기사, 범인 검거 및 송치 뉴스, 실제 피해자의 순수 정보 공유글은 'INFO'
    2. 법무법인/변호사의 홍보 및 상담 유도글은 'AD'
    3. '불법사금융예방대출' 등 대출을 알선하거나 권유하는 글은 'AD'
    4. '피해구제 상담', '법적 대응'을 도와주겠다며 특정 오픈채팅이나 연락처로 유인하는 글은 'AD'
    
    제목: {title}
    내용: {description}
    
    결과값으로 오직 'AD' 또는 'INFO' 만 출력하세요.
    """
    try:
        response = model.generate_content(prompt)
        return "AD" in response.text.strip().upper()
    except:
        return False

# --- 메인 실행 로직 ---
if st.button("🚀 지금 모니터링 시작", type="primary"):
    raw_results = []
    
    with st.spinner("데이터 수집 및 AI 광고 필터링, 유사도 분석 중입니다. 잠시만 기다려주세요..."):
        # 1. 데이터 수집
        for kw in keywords_list:
            for cat in ['news', 'blog', 'cafearticle']:
                items = search_naver(cat, kw)
                for item in items:
                    title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                    
                    # 2. 필수 포함 문구 1차 필터링 (빠른 속도를 위해 AI 전에 텍스트로 걸러냄)
                    if mandatory_list:
                        if not any(m in title or m in desc for m in mandatory_list):
                            continue # 필수 문구가 하나도 없으면 패스
                    
                    # 데이터 정제 및 날짜 포맷팅
                    date_key = 'pubDate' if cat == 'news' else 'postdate'
                    raw_date = item.get(date_key, '')
                    
                    raw_results.append({
                        'category': cat,
                        'origin_kw': kw,
                        'title': title,
                        'desc': desc,
                        'link': item['link'],
                        'date': format_date(raw_date, cat)
                    })

        # 3. AI 필터링 (필수 문구를 통과한 데이터만 AI 검사하여 비용 및 시간 절약)
        filtered_results = []
        for item in raw_results:
            # 1차적으로 노골적인 단어가 포함된 글은 AI 검사 없이 바로 필터링 (비용 최적화)
            hard_ads_keywords = ["예방대출", "피해구제 상담", "법무법인", "무료상담"]
            if any(ad_kw in item['title'] or ad_kw in item['desc'] for ad_kw in hard_ads_keywords):
                continue
                
            if not is_ad_by_gemini(item['title'], item['desc']):
                filtered_results.append(item)

        # 4. 유사 기사 클러스터링 (비슷한 기사 묶기)
        grouped_results = []
        for item in filtered_results:
            found_group = False
            for group in grouped_results:
                # 그룹의 대표 기사(첫 번째 기사)와 제목 유사도 비교
                if is_similar(item['title'], group[0]['title']):
                    group.append(item)
                    found_group = True
                    break
            if not found_group:
                grouped_results.append([item])
        
        # --- 결과 출력 ---
        if not grouped_results:
            st.warning("조건에 맞는 수집된 데이터가 없습니다. 검색어나 필수 포함 문구를 조정해 보세요.")
        else:
            st.success(f"총 {len(grouped_results)}개의 고유한 이슈가 발견되었습니다.")
            
            for group in grouped_results:
                main_item = group[0]
                badge = get_category_badge(main_item['category'])
                
                with st.container():
                    # 상단: 카테고리, 제목, 날짜 구성
                    col_badge, col_title, col_date = st.columns([1.5, 7, 1.5])
                    with col_badge:
                        st.markdown(badge)
                    with col_title:
                        st.markdown(f"**[{main_item['title']}]({main_item['link']})**")
                    with col_date:
                        st.caption(f"{main_item['date']}")
                    
                    # 하단: 본문 요약 및 키워드
                    st.write(f"<span style='color:gray; font-size:14px'>{main_item['desc']}</span>", unsafe_allow_html=True)
                    st.caption(f"검색 키워드: {main_item['origin_kw']}")
                    
                    # 유사 기사가 있는 경우 접어두기(Expander)로 구현
                    if len(group) > 1:
                        with st.expander(f"🔗 비슷한 내용의 다른 글 {len(group)-1}개 더보기"):
                            for sub_item in group[1:]:
                                sub_badge = get_category_badge(sub_item['category'])
                                st.markdown(f"{sub_badge} [{sub_item['title']}]({sub_item['link']}) | <span style='font-size:12px; color:gray'>{sub_item['date']}</span>", unsafe_allow_html=True)
                    st.divider()

else:
    st.info("좌측 사이드바에서 키워드 및 필수 포함 문구를 확인하고 모니터링 시작 버튼을 눌러주세요.")
