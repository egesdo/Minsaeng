import streamlit as st
import requests
import google.generativeai as genai
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
import json

# --- 애플 스타일 UI 및 강제 여백 제거 CSS ---
st.set_page_config(page_title="Fin-Light | 통합 대시보드", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
        /* 폰트 및 전체 배경 */
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/variable/pretendardvariable.css');
        html, body, [class*="css"], .stApp {
            font-family: 'Pretendard Variable', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif !important;
            background-color: #FBFBFD !important;
        }
        
        /* 워터마크 및 헤더/푸터 완벽 제거 */
        header[data-testid="stHeader"] { display: none !important; } 
        footer { display: none !important; } 
        .stDeployButton { display: none !important; } 
        #MainMenu { display: none !important; }
        
        /* 메인 컨테이너 여백 0 강제화 */
        .block-container {
            padding: 0rem !important;
            margin: 0rem !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        
        /* 사이드바 상단 여백 제거 및 디자인 */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E5E5EA !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.5rem !important; 
        }
        
        /* Apple 스타일 UI 요소 */
        .stTextInput input, .stTextArea textarea {
            border-radius: 10px !important;
            border: 1px solid #D2D2D7 !important;
            transition: all 0.2s ease;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #0071E3 !important;
            box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
        }
        .stButton > button {
            border-radius: 980px !important; 
            background-color: #0071E3 !important;
            color: #FFFFFF !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease !important;
            width: 100%;
        }
        .stButton > button:hover {
            background-color: #0077ED !important;
            transform: scale(0.98);
        }

        /* Fin-Light 타이틀 박스 */
        .apple-title-box {
            background: linear-gradient(135deg, #F5F5F7 0%, #FFFFFF 100%);
            border: 1px solid #E5E5EA;
            border-radius: 16px;
            padding: 18px 15px;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        }
        .apple-title-text {
            font-size: 22px;
            font-weight: 800;
            color: #1D1D1F;
            letter-spacing: -0.5px;
        }
        .apple-subtitle-text {
            font-size: 11px;
            color: #86868B;
            margin-top: 4px;
            font-weight: 500;
        }

        /* 4분할 화면용 커스텀 그리드 */
        .perfect-grid {
            display: flex;
            flex-wrap: wrap;
            width: 100%;
            height: 100vh;
        }
        .perfect-grid iframe {
            width: 50%;
            height: 50vh;
            border: 1px solid #E5E5EA;
            border-top: none;
            border-left: none;
            box-sizing: border-box;
            background-color: #FFFFFF;
        }
        
        /* 엔티티 태그 스타일 */
        .entity-tag {
            background-color: #E8F0FE; 
            color: #1967D2; 
            padding: 3px 8px; 
            border-radius: 6px; 
            font-size: 11px; 
            font-weight: 700; 
            margin-right: 5px; 
            display: inline-block;
            margin-bottom: 5px;
        }
        /* AI 결과 박스 패딩 */
        .ai-result-container { padding: 30px; max-width: 1200px; margin: 0 auto; }
    </style>
""", unsafe_allow_html=True)

# --- 보안 및 API 설정 ---
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

# --- 사이드바 구성 ---
with st.sidebar:
    st.markdown("""
        <div class="apple-title-box">
            <div class="apple-title-text"><span>🔦</span> Fin-Light</div>
            <div class="apple-subtitle-text">민생금융범죄 모니터링 대시보드</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🤖 AI 정밀 모니터링</h4>", unsafe_allow_html=True)
    selected_category = st.radio("카테고리", options=list(CATEGORY_KEYWORDS.keys()), label_visibility="collapsed")
    current_keywords = st.text_area("AI 검색어", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=70)
    mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
    
    if st.button("AI 분석 모드 열기", key="btn_ai"):
        st.session_state.view_mode = "AI"

    st.markdown("<div style='margin-top:30px;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='font-size:14px; color:#1D1D1F;'>🔍 통합 다중 검색 (4분할)</h4>", unsafe_allow_html=True)
    multi_query = st.text_input("검색어 입력 후 엔터", placeholder="예: 선이자", key="multi_search_input")
    
    if multi_query:
        st.session_state.view_mode = "MULTI"

if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "AI"

# --- [VIEW 1] 4분할 다중 검색 모드 ---
if st.session_state.view_mode == "MULTI" and multi_query:
    q = quote(multi_query)
    urls = [
        f"https://m.search.naver.com/search.naver?query={q}",
        f"https://www.google.com/search?q={q}&igu=1",
        f"https://m.search.daum.net/search?w=tot&q={q}",
        f"https://www.bing.com/search?q={q}"
    ]
    html_code = f"""
        <div class="perfect-grid">
            <iframe src="{urls[0]}"></iframe>
            <iframe src="{urls[1]}"></iframe>
            <iframe src="{urls[2]}"></iframe>
            <iframe src="{urls[3]}"></iframe>
        </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

# --- [VIEW 2] AI 정밀 모니터링 모드 ---
else:
    def search_naver(category, query, display=35):
        url = f"https://openapi.naver.com/v1/search/{category}.json"
        headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
        params = {"query": query, "display": display, "sort": "date"}
        response = requests.get(url, headers=headers, params=params)
        return response.json().get('items', []) if response.status_code == 200 else []

    def is_hard_ad(title, desc):
        ad_keywords = ["법무법인", "변호사", "법률사무소", "수임료", "승소", "고소대리", "상담문의", "해결사", "무료법률상담"]
        return any(kw in (title + desc) for kw in ad_keywords)

    def analyze_with_gemini(title, desc, category_name):
        prompt = f"""
        금융범죄 분석가로서 아래 글을 분석하여 JSON 형식으로만 답변하세요.
        - INFO: 실제 사건 보도(검거/송치), 피해자의 구체적 피해 호소/질문
        - AD: 법무법인 광고, 일반적 범죄 수법 교육/공지글
        - 추출: 글에 언급된 구체적 코인명, 플랫폼명, 가명(OO팀장 등), 사이트 주소
        제목: {title}
        내용: {desc}
        출력 형식: {{"status": "INFO" 또는 "AD", "entities": ["키워드1", "키워드2"]}}
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

    st.markdown(f"<div class='ai-result-container'><h2 style='color:#1D1D1F; font-weight:800; letter-spacing:-1px;'>🤖 {selected_category} AI 정밀 분석 모드</h2><p style='color:#86868B;'>우측 하단 검색창에 단어를 입력하면 4분할 화면으로 전환됩니다.</p><br>", unsafe_allow_html=True)
    
    if st.button("🚀 정밀 분석 실행", key="run_ai_btn"):
        raw_results = []
        base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
        mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
        
        with st.spinner("가비지 데이터를 걸러내고 핵심 개체를 추출 중입니다..."):
            search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

            for query in search_queries:
                for cat in ['news', 'blog', 'cafearticle']:
                    items = search_naver(cat, query)
                    for item in items:
                        title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                        desc = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", "'")
                        
                        if is_hard_ad(title, desc): continue
                        
                        raw_date = item.get('pubDate' if cat == 'news' else 'postdate', '')
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

            unique_results = list({it['link']: it for it in raw_results}.values())
            final_display = []
            
            for item in unique_results[:40]: 
                is_valid, entities = analyze_with_gemini(item['title'], item['desc'], selected_category)
                if is_valid:
                    item['entities'] = entities
                    final_display.append(item)

            if not final_display:
                st.warning("유효한 데이터가 없습니다. 필수 포함 단어를 조정해 보세요.")
            else:
                st.success(f"필터링 완료. {len(final_display)}건의 주요 정보가 추출되었습니다.")
                for item in final_display:
                    with st.container():
                        st.markdown(f"{get_badge(item['category'])} <a href='{item['link']}' target='_blank' style='text-decoration:none; color:#1D1D1F; font-size:16px; font-weight:600;'>{item['title']}</a> <span style='float:right; font-size:12px; color:#86868B;'>{item['date_str']}</span>", unsafe_allow_html=True)
                        
                        if item.get('entities'):
                            entity_html = "".join([f"<span class='entity-tag'>{e}</span>" for e in item['entities']])
                            st.markdown(entity_html, unsafe_allow_html=True)
                        
                        st.markdown(f"<div style='font-size:13px; color:#444; background-color:#FFFFFF; border:1px solid #E5E5EA; padding:10px 12px; border-radius:10px; margin-top:6px; box-shadow:0 1px 3px rgba(0,0,0,0.02);'><b>출처: {item['source']}</b><br><span style='color:#666;'>{item['desc']}</span></div>", unsafe_allow_html=True)
                        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
