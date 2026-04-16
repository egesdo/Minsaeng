import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime

# --- Streamlit Secrets를 이용한 보안 설정 ---
# 배포 후 Streamlit Cloud의 'Advanced Settings' > 'Secrets'에 직접 입력해야 합니다.
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("API 키 설정이 필요합니다. Streamlit Cloud의 Secrets 설정을 확인해주세요.")
    st.stop()

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 페이지 레이아웃 설정 ---
st.set_page_config(page_title="Fin-Light | 민생금융범죄 모니터링", layout="wide")

st.title("🔦 Fin-Light | 민생금융범죄 모니터링 시스템")
st.caption("불법사금융, 유사수신, 리딩방 관련 온라인 최신 정보를 통합 모니터링합니다.")

# --- 사이드바: 키워드 관리 ---
with st.sidebar:
    st.header("⚙️ 모니터링 설정")
    default_keywords = "불법사금융, 리딩방 사기, 원금보장 투자, 작업대출, 비상장주식 리딩"
    user_keywords = st.text_area("모니터링 키워드 (쉼표로 구분)", value=default_keywords, height=100)
    keywords_list = [k.strip() for k in user_keywords.split(",")]
    
    st.divider()
    st.info("AI가 광고성 게시글(법무법인 홍보 등)을 자동으로 필터링합니다.")

# --- 기능 함수 ---
def search_naver(category, query, display=10):
    """네이버 검색 API 호출"""
    url = f"https://openapi.naver.com/v1/search/{category}.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": display, "sort": "sim"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

def is_ad_by_gemini(title, description):
    """Gemini AI를 이용한 광고 여부 판별"""
    prompt = f"""
    당신은 민생금융범죄 수사관입니다. 다음 글이 불법사금융 피해자의 실제 후기나 정보 공유인지, 
    아니면 법무법인/변호사의 홍보글 또는 대출 광고인지 판별하세요.
    
    제목: {title}
    내용: {description}
    
    광고나 홍보글이면 'AD', 실제 정보성 글이면 'INFO'라고만 답하세요.
    """
    try:
        response = model.generate_content(prompt)
        return "AD" in response.text.strip().upper()
    except:
        return False

# --- 메인 화면: 데이터 수집 및 표시 ---
if st.button("지금 모니터링 시작"):
    all_results = []
    
    with st.spinner("네이버 데이터를 수집하고 AI 분석 중입니다..."):
        for kw in keywords_list:
            for cat in ['news', 'blog', 'cafearticle']:
                items = search_naver(cat, kw)
                for item in items:
                    item['category'] = cat
                    item['origin_kw'] = kw
                    all_results.append(item)
        
        if not all_results:
            st.warning("수집된 데이터가 없습니다.")
        else:
            for idx, item in enumerate(all_results[:30]):
                title = item['title'].replace("<b>", "").replace("</b>", "")
                desc = item['description'].replace("<b>", "").replace("</b>", "")
                link = item['link']
                
                is_ad = is_ad_by_gemini(title, desc)
                
                if not is_ad:
                    with st.container():
                        col1, col2 = st.columns([1, 8])
                        with col1:
                            st.write(f"[{item['category'].upper()}]")
                        with col2:
                            st.markdown(f"#### [{title}]({link})")
                            st.write(f"**키워드:** {item['origin_kw']} | {desc}")
                            st.divider()
    st.success("모니터링이 완료되었습니다.")
else:
    st.info("사이드바에서 키워드를 확인하고 '모니터링 시작' 버튼을 눌러주세요.")
