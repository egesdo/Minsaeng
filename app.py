import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timedelta
import urllib.parse
import json
import re
from difflib import SequenceMatcher

# --- 1. 기본 설정 (가장 안정적인 순정 레이아웃) ---
# 레이아웃은 'wide'로 설정하되, 무리한 CSS 조작은 모두 제거했습니다.
st.set_page_config(page_title="Fin-Light | 모니터링 시스템", layout="wide", initial_sidebar_state="expanded")

# 핵심 CSS (최소한의 가독성 개선만 적용)
st.markdown("""
    <style>
    /* 상하단 불필요한 기본 여백 최소화 */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* 엔티티 태그 (코인명, 가명 등 강조) */
    .entity-tag {
        background-color: #E6F3FF; 
        color: #0066CC; 
        padding: 4px 8px; 
        border-radius: 4px; 
        font-size: 12px; 
        font-weight: bold; 
        margin-right: 6px; 
        display: inline-block;
    }
    
    /* 카드형 UI 스타일 */
    .result-card {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 15px;
        margin-top: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 환경 설정 및 API 키 확인 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("⚠️ Streamlit Cloud의 Secrets 설정에서 GEMINI_API_KEY를 입력해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 모니터링 기본 키워드 셋
CATEGORY_KEYWORDS = {
    "불법사금융": ["선이자", "연장비", "지각비", "수치심", "지인추심", "3050대출", "폰깡", "대부중개사이트 피해"],
    "리딩방": ["리딩방 입금", "출금거부", "환급수수료", "금융감독원 사칭", "교수 사칭", "코인 리딩방 피해"],
    "유사수신": ["상장 예정 코인", "원금보장 투자", "스테이킹 사기", "프라이빗 세일 사기", "다단계 코인"]
}

# --- 3. 사이드바 및 네비게이션 ---
with st.sidebar:
    st.title("🔦 Fin-Light")
    st.caption("민생금융범죄 모니터링 시스템")
    st.divider()
    
    # 순정 라디오 버튼으로 메뉴 구성
    page = st.radio("기능 선택", ["🤖 AI 정밀 분석", "🔍 다중 검색 엔진 (4분할)"])
    st.divider()

# ==========================================
# 기능 1 : AI 정밀 분석 (웹 크롤링)
# ==========================================
if page == "🤖 AI 정밀 분석":
    
    with st.sidebar:
        st.subheader("⚙️ 모니터링 설정")
        selected_category = st.radio("범죄 유형", options=list(CATEGORY_KEYWORDS.keys()))
        current_keywords = st.text_area("검색어 (쉼표 구분)", value=", ".join(CATEGORY_KEYWORDS[selected_category]), height=100)
        mandatory_keywords = st.text_input("필수 포함 단어", value="송치, 검거, 구속, 피해")
        date_filter = st.selectbox("검색 기간", ["최근 1개월", "최근 3개월", "최근 1년", "전체"])
        
        run_btn = st.button("🚀 정밀 분석 시작", use_container_width=True)

    st.header(f"🤖 {selected_category} 정밀 분석 대시보드")
    st.write("네이버 검색 결과를 실시간으로 수집하고, AI가 핵심 정보를 추출합니다.")

    if run_btn:
        # --- 유틸리티 함수 ---
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
            
            # 뉴스
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
            except Exception as e:
                pass # 크롤링 에러 무시
                
            # 블로그/카페 (뷰)
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
            except Exception as e:
                pass

            return results

        def analyze_with_gemini(title, desc):
            prompt = f"""
            금융범죄 분석가로서 아래 글을 분석하여 JSON 형식으로만 답변하세요.
            - INFO: 실제 사건 보도(검거/송치), 피해자의 구체적 피해 호소/질문
            - AD: 법무법인/변호사 광고, 대출 광고, 단순 수법 교육글
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

        def get_badge(cat):
            if cat == 'news': return "🔵 **[뉴스]**"
            elif cat == 'blog': return "🟢 **[블로그]**"
            return "🔴 **[카페]**"

        # --- 메인 실행 로직 ---
        now = datetime.now()
        if date_filter == "최근 1개월": limit_date = now - timedelta(days=30)
        elif date_filter == "최근 3개월": limit_date = now - timedelta(days=90)
        elif date_filter == "최근 1년": limit_date = now - timedelta(days=365)
        else: limit_date = None

        raw_results = []
        base_kws = [k.strip() for k in current_keywords.split(",") if k.strip()]
        mand_kws = [m.strip() for m in mandatory_keywords.split(",") if m.strip()]
        
        with st.spinner("웹 데이터를 스크래핑하고 AI 분석을 진행하고 있습니다. 잠시만 기다려주세요..."):
            search_queries = [f"{b} {m}" for b in base_kws for m in mand_kws] if mand_kws else base_kws

            # 1. 크롤링 수집
            for query in search_queries:
                crawled_items = crawl_naver(query)
                for item in crawled_items:
                    # 1차 광고 텍스트 필터링
                    ad_kws = ["법무법인", "변호사", "수임료", "승소", "고소대리", "무료상담"]
                    if any(kw in (item['title'] + item['desc']) for kw in ad_kws): continue
                    
                    dt_obj = parse_korean_date(item['raw_date'])
                    if limit_date and dt_obj < limit_date: continue
                    
                    item['datetime'] = dt_obj
                    item['date_str'] = dt_obj.strftime("%Y-%m-%d")
                    raw_results.append(item)

            # 2. 중복 제거 및 시간순 정렬
            unique_results = list({it['link']: it for it in raw_results}.values())
            unique_results.sort(key=lambda x: x['datetime'], reverse=True)
            
            # 3. AI 분석 (상위 30건 제한)
            valid_results = []
            for item in unique_results[:30]: 
                is_valid, entities = analyze_with_gemini(item['title'], item['desc'])
                if is_valid:
                    item['entities'] = entities
                    valid_results.append(item)

            # 4. 유사 글 묶기 (클러스터링)
            grouped_results = []
            for item in valid_results:
                found_group = False
                for group in grouped_results:
                    if SequenceMatcher(None, item['title'], group[0]['title']).ratio() > 0.5:
                        group.append(item)
                        found_group = True
                        break
                if not found_group: grouped_results.append([item])

            # 5. 결과 화면 출력
            st.divider()
            if not grouped_results:
                st.warning("조건에 맞는 유효한 데이터가 없습니다. 검색어나 기간을 조정해 보세요.")
            else:
                st.success(f"분석 완료! 총 {len(grouped_results)}개의 주요 이슈가 발견되었습니다.")
                
                for group in grouped_results:
                    main = group[0]
                    
                    # 순정 Streamlit 컨테이너를 활용한 깔끔한 UI
                    with st.container():
                        st.markdown(f"### {get_badge(main['category'])} [{main['title']}]({main['link']})")
                        
                        col1, col2 = st.columns([8, 2])
                        with col1:
                            if main.get('entities'):
                                st.markdown("".join([f"<span class='entity-tag'># {e}</span>" for e in main['entities']]), unsafe_allow_html=True)
                        with col2:
                            st.write(f"📅 {main['date_str']}")
                        
                        st.markdown(f"<div class='result-card'><b>출처: {main['source']}</b><br><span style='color:#555;'>{main['desc']}</span></div>", unsafe_allow_html=True)
                        
                        if len(group) > 1:
                            with st.expander(f"🔗 비슷한 내용의 기사/게시글 {len(group)-1}개 더보기"):
                                for sub in group[1:]:
                                    st.markdown(f"- {get_badge(sub['category'])} [{sub['title']}]({sub['link']}) ({sub['source']} / {sub['date_str']})")
                        
                        st.markdown("---") # 구분선

# ==========================================
# 기능 2 : 4분할 다중 검색 모드
# ==========================================
elif page == "🔍 다중 검색 엔진 (4분할)":
    st.header("🔍 다중 검색 엔진 모니터링")
    st.write("네이버, 구글, 다음, 빙(Bing)의 검색 결과를 한눈에 비교합니다.")
    
    with st.form("multi_search"):
        col_input, col_btn = st.columns([8, 2])
        with col_input:
            multi_query = st.text_input("검색어를 입력하세요", placeholder="예: 불법사금융 송치", label_visibility="collapsed")
        with col_btn:
            search_submitted = st.form_submit_button("4분할 검색", use_container_width=True)

    if search_submitted and multi_query:
        q = urllib.parse.quote(multi_query)
        
        # 순정 Streamlit 컬럼 분할 기능을 사용하여 안전하게 2x2 배치
        col1, col2 = st.columns(2)
        
        # 높이를 500px로 고정하여 화면 찌그러짐 원천 차단
        iframe_style = "width:100%; height:500px; border:1px solid #ccc; border-radius:5px;"
        
        with col1:
            st.markdown("**🟢 네이버**")
            st.markdown(f'<iframe src="https://m.search.naver.com/search.naver?query={q}" style="{iframe_style}"></iframe>', unsafe_allow_html=True)
            
            st.markdown("**🟡 다음**")
            st.markdown(f'<iframe src="https://m.search.daum.net/search?w=tot&q={q}" style="{iframe_style}"></iframe>', unsafe_allow_html=True)
            
        with col2:
            st.markdown("**🔵 구글**")
            st.markdown(f'<iframe src="https://www.google.com/search?q={q}&igu=1" style="{iframe_style}"></iframe>', unsafe_allow_html=True)
            
            st.markdown("**🌐 Bing**")
            st.markdown(f'<iframe src="https://www.bing.com/search?q={q}" style="{iframe_style}"></iframe>', unsafe_allow_html=True)

    elif search_submitted and not multi_query:
        st.warning("검색어를 입력해 주세요.")
