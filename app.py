import streamlit as st
import streamlit.components.v1 as components
import urllib.parse

# --- UI 설정 ---
st.set_page_config(page_title="Fin-Light | 4분할 다중 검색", layout="wide")
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        #MainMenu, header, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🔍 Fin-Light | 다중 검색엔진 4분할 비교")
st.warning("⚠️ 네이버/구글/다음은 자체 보안 정책으로 인해 일반 화면에서는 조회가 차단됩니다. 정상 조회를 위해 크롬 확장 프로그램(Ignore X-Frame Headers 등)을 활성화해 주세요.")

# 검색창
query = st.text_input("모니터링할 검색어를 입력하세요", value="불법사금융 송치")
encoded_query = urllib.parse.quote(query)

if st.button("🚀 4분할 검색 실행", type="primary"):
    
    # 각 포털의 모바일웹 검색 URL (모바일 화면 비율에 맞추기 위함)
    naver_url = f"https://m.search.naver.com/search.naver?query={encoded_query}"
    google_url = f"https://www.google.com/search?q={encoded_query}"
    daum_url = f"https://m.search.daum.net/search?w=tot&q={encoded_query}"
    
    # 4번째 엔진: DuckDuckGo (얀덱스로 원하실 경우 아래 주석 해제)
    fourth_url = f"https://duckduckgo.com/?q={encoded_query}"
    # fourth_url = f"https://yandex.com/search/?text={encoded_query}" 
    
    # 2x2 그리드 분할 (비율 1:1)
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    # iframe 스타일 (모바일 비율처럼 보이도록 폭을 100%로 하고 스크롤 허용)
    iframe_style = "width: 100%; height: 600px; border: 2px solid #ddd; border-radius: 8px;"
    
    with col1:
        st.markdown("<h4 style='color:#03C75A;'>🟢 네이버 (모바일)</h4>", unsafe_allow_html=True)
        components.html(f'<iframe src="{naver_url}" style="{iframe_style}"></iframe>', height=610)
        
    with col2:
        st.markdown("<h4 style='color:#4285F4;'>🔵 구글 (모바일)</h4>", unsafe_allow_html=True)
        components.html(f'<iframe src="{google_url}" style="{iframe_style}"></iframe>', height=610)
        
    with col3:
        st.markdown("<h4 style='color:#FFCD00;'>🟡 다음 (모바일)</h4>", unsafe_allow_html=True)
        components.html(f'<iframe src="{daum_url}" style="{iframe_style}"></iframe>', height=610)
        
    with col4:
        st.markdown("<h4>🦆 DuckDuckGo (또는 Yandex)</h4>", unsafe_allow_html=True)
        components.html(f'<iframe src="{fourth_url}" style="{iframe_style}"></iframe>', height=610)
