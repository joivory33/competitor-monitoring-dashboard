import streamlit as st
import pandas as pd
import requests
import datetime
import email.utils
import base64
import re

# 1. 페이지 설정
st.set_page_config(
    page_title="경쟁사 마켓 트렌드 모니터링",
    page_icon="📰",
    layout="wide"
)

# 💡 사이드바 내부의 코드 블록(code)과 pre 태그가 가로 너비를 초과하지 않고 자동 줄바꿈되도록 강제 설정
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] pre, [data-testid="stSidebar"] code {
        white-space: pre-wrap !important;
        word-break: break-all !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📰 경쟁사 뉴스 및 블로그 모니터링 요약")
st.markdown("설정한 기간 동안 **하나투어, 여기어때, 트립닷컴, 에어비앤비, 모두투어, 클룩, NOL** 관련 핵심 동향을 분석합니다.")

# -----------------------------------------------------------------
# 🔑 [자동 저장 기능] URL 파라미터에서 기존에 저장된 API 키 복구하기
# -----------------------------------------------------------------
def encode_key(val):
    """보안을 위해 API 키 값을 가볍게 base64로 인코딩합니다."""
    return base64.b64encode(val.encode()).decode() if val else ""

def decode_key(val):
    """인코딩된 값을 원래 API 키로 디코딩합니다."""
    try:
        return base64.b64decode(val.encode()).decode() if val else ""
    except Exception:
        return ""

# 주소창(Query Params)에 이미 저장된 키가 있는지 확인하여 자동 로그인 세팅
query_params = st.query_params
saved_id = decode_key(query_params.get("cid", ""))
saved_secret = decode_key(query_params.get("csec", ""))

if "naver_client_id" not in st.session_state:
    st.session_state.naver_client_id = saved_id
if "naver_client_secret" not in st.session_state:
    st.session_state.naver_client_secret = saved_secret
if "api_authenticated" not in st.session_state:
    st.session_state.api_authenticated = bool(saved_id and saved_secret)

# API 인증 UI 및 로그인 제어
if not st.session_state.api_authenticated:
    st.markdown("### 🔑 실시간 데이터 수집을 위한 API 인증")
    st.info("실시간 동향 수집을 시작하려면 아래에 네이버 검색 API 인증키를 입력해 주세요.")
    
    col_id, col_secret = st.columns(2)
    with col_id:
        input_id = st.text_input("Naver Client ID", type="password", key="temp_id")
    with col_secret:
        input_secret = st.text_input("Naver Client Secret", type="password", key="temp_secret")
    
    remember_me = st.checkbox("💾 내 브라우저에 이 API 키 기억하기 (이 대시보드를 북마크에 추가해 쓰세요!)", value=True)
        
    if st.button("🔑 인증키 등록 및 로그인"):
        if input_id and input_secret:
            st.session_state.naver_client_id = input_id
            st.session_state.naver_client_secret = input_secret
            st.session_state.api_authenticated = True
            if remember_me:
                st.query_params["cid"] = encode_key(input_id)
                st.query_params["csec"] = encode_key(input_secret)
            st.rerun()
        else:
            st.error("Client ID와 Client Secret을 모두 입력해 주세요.")
else:
    col_status, col_btn = st.columns([5, 1])
    with col_status:
        st.success("✅ 네이버 API 인증 완료 - 대시보드가 정상 가동 중입니다.")
    with col_btn:
        if st.button("🔌 API 인증 정보 초기화"):
            st.session_state.naver_client_id = ""
            st.session_state.naver_client_secret = ""
            st.session_state.api_authenticated = False
            st.query_params.clear()
            st.rerun()

# -----------------------------------------------------------------
# 2. 사이드바 구성 (설정 필터 및 가이드)
# -----------------------------------------------------------------
st.sidebar.header("🔍 설정 필터")

today = datetime.date.today()
start_date = st.sidebar.date_input("시작일", today - datetime.timedelta(days=7))
end_date = st.sidebar.date_input("종료일", today)

brands = ["하나투어", "여기어때", "트립닷컴", "에어비앤비", "모두투어", "클룩", "놀(NOL)"]
selected_brands = st.sidebar.multiselect(
    "모니터링 대상 브랜드",
    options=brands,
    default=brands
)

channels = st.sidebar.multiselect(
    "수집 채널",
    options=["뉴스", "블로그"],
    default=["뉴스", "블로그"]
)

# 💡 [신규] 중복(유사 이슈) 묶기 민감도 조절 슬라이더
cluster_threshold = st.sidebar.slider(
    "🧩 중복 기사 묶기 민감도",
    min_value=0.15, max_value=0.60, value=0.28, step=0.01,
    help="값이 낮을수록 비슷한 주제의 기사를 더 넓게 하나로 묶습니다. (너무 많이 묶이면 값을 올리세요)"
)

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 네이버 API 발급 가이드")

with st.sidebar.expander("📍 [필독] 1분 API 발급 가이드", expanded=True):
    st.markdown("""
    ### 1️⃣ 애플리케이션 등록 및 API 선택
    * **이름:** `검색 키워드` 입력
    * **사용 API:** 목록에서 **[네이버 로그인]** 선택
    
    ### 2️⃣ 제공 정보 설정
    *보안 심사 없이 바로 키를 발급받기 위해 아래 3가지 항목만 간략히 선택해 주세요.*
    * **회원이름, 성별, 출생연도**만 필수/추가로 체크 (나머지는 모두 체크 해제)
    
    ### 3️⃣ 서비스 환경 설정 (PC 웹)
    * **환경 추가:** **[PC 웹]** 선택 후 등록
    * **서비스 URL 및 Callback URL:** 아래 주소를 두 곳 모두 동일하게 입력합니다.
    
    ```text
    https://instagram-insight-dashboard-yfksdz8sudm8rqyrxy3cqz.streamlit.app/
    ```
    """)

# API 로직 바인딩
client_id = st.session_state.naver_client_id
client_secret = st.session_state.naver_client_secret


# 3. 네이버 날짜 데이터 파싱 함수
def parse_naver_date(date_str, item_type):
    if not date_str:
        return None
    try:
        if item_type == "news":
            parsed_dt = email.utils.parsedate_to_datetime(date_str)
            return parsed_dt.date()
        elif item_type == "blog":
            return datetime.datetime.strptime(str(date_str).strip(), "%Y%m%d").date()
    except Exception:
        return None


# -----------------------------------------------------------------
# 4. [핵심 로직] 유사 이슈 클러스터링 (하이브리드: 키워드 겹침 + 글자 유사도)
# -----------------------------------------------------------------
# 제목에서 자주 등장하지만 변별력이 없는 단어(불용어) 목록
STOPWORDS = {
    "대표", "신임", "출범", "전환", "발표", "공개", "진행", "기념", "선포",
    "체제", "회사", "기업", "관련", "위해", "통해", "이번", "지난", "오는", "역시"
}

def extract_keywords(text):
    """제목에서 핵심 키워드(2글자 이상 한글 / 영문·숫자 토큰)를 추출합니다."""
    t = text.lower().replace("chapter", "챕터").replace("號", "")
    t = re.sub(r"[^0-9a-z가-힣]+", " ", t)
    words = set()
    for w in t.split():
        w = w.strip()
        if not w or w in STOPWORDS:
            continue
        if re.fullmatch(r"[가-힣]", w):  # 한 글자짜리 한글은 제외
            continue
        words.add(w)
    return words


def get_char_ngrams(text, n=2):
    clean_text = "".join(text.split())
    return set(clean_text[i:i + n] for i in range(len(clean_text) - n + 1))


def hybrid_similarity(title1, title2):
    """키워드 자카드 유사도와 글자 n-gram 자카드 유사도 중 더 높은 값을 반환합니다."""
    if not title1 or not title2:
        return 0.0
    # (1) 키워드 겹침
    k1, k2 = extract_keywords(title1), extract_keywords(title2)
    k_union = len(k1 | k2)
    word_sim = len(k1 & k2) / k_union if k_union else 0.0
    # (2) 글자 조합 겹침
    c1, c2 = get_char_ngrams(title1), get_char_ngrams(title2)
    c_union = len(c1 | c2)
    char_sim = len(c1 & c2) / c_union if c_union else 0.0
    return max(word_sim, char_sim)


def build_cluster_table(df_brand, threshold):
    """브랜드별 기사를 유사 이슈로 묶어 대표 1건 + 관련 건수 형태의 표로 반환합니다."""
    if df_brand.empty:
        return pd.DataFrame()

    clusters = []  # 각 원소: {'rep_idx': 대표행 인덱스, 'members': [행 dict, ...]}
    for _, row in df_brand.iterrows():
        title = row["제목"]
        placed = False
        for c in clusters:
            if hybrid_similarity(title, c["rep"]["제목"]) >= threshold:
                c["members"].append(row)
                placed = True
                break
        if not placed:
            clusters.append({"rep": row, "members": [row]})

    rows = []
    for c in clusters:
        rep = c["rep"]
        rows.append({
            "관련 기사 수": len(c["members"]),
            "구분": rep["구분"],
            "대표 제목": rep["제목"],
            "요약본": rep["요약본"],
            "대표 링크": rep["원문 링크"],
            "게시일": rep["게시일"],
        })

    table = pd.DataFrame(rows).sort_values(
        "관련 기사 수", ascending=False
    ).reset_index(drop=True)
    return table


# 5. 데이터 수집 및 정제 함수
def fetch_naver_data(query, search_type, start_dt, end_dt):
    if not client_id or not client_secret:
        return None
        
    url = f"https://openapi.naver.com/v1/search/{search_type}.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": 100,
        "sort": "sim"
    }
    
    clean_query = query.split("(")[0].strip()
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            res_json = response.json()
            items = res_json.get("items", [])
            data_list = []
            
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                description = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                link = item['link']
                
                text_to_check = (title + " " + description).lower()
                
                # 브랜드 키워드 검증
                if query == "놀(NOL)":
                    if "놀 카드" not in text_to_check and "nol 카드" not in text_to_check and "야놀자" not in text_to_check:
                        continue
                else:
                    if clean_query.lower() not in text_to_check:
                        continue
                
                raw_pub_date = item.get('pubDate') if search_type == "news" else item.get('postdate')
                parsed_date = parse_naver_date(raw_pub_date, search_type)
                
                if parsed_date:
                    if not (start_dt <= parsed_date <= end_dt):
                        continue
                
                data_list.append({
                    "브랜드": query,
                    "구분": "뉴스" if search_type == "news" else "블로그",
                    "제목": title,
                    "요약본": description,
                    "원문 링크": link,
                    "게시일": parsed_date if parsed_date else raw_pub_date
                })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 오류 ({query}): {e}")
    return None


# -----------------------------------------------------------------
# 6. [개선] 브랜드별 상세 동향 브리핑 생성기
# -----------------------------------------------------------------
def generate_brand_briefing(brand, df_brand, cluster_df):
    if df_brand.empty:
        return "선택하신 기간 내 수집된 활동 데이터가 없습니다."

    total = len(df_brand)
    news_count = int((df_brand["구분"] == "뉴스").sum())
    blog_count = int((df_brand["구분"] == "블로그").sum())

    unique_count = len(cluster_df)          # 실제 핵심 이슈 수
    dup_count = total - unique_count        # 유사·중복으로 묶여 정리된 건수

    # 수집 기간(실제 날짜가 있는 것만 계산)
    valid_dates = [d for d in df_brand["게시일"] if isinstance(d, datetime.date)]
    if valid_dates:
        period_txt = f"{min(valid_dates)} ~ {max(valid_dates)}"
    else:
        period_txt = "기간 정보 없음"

    brief = f"### 📢 {brand} 동향 브리핑\n"
    brief += f"- 📊 **수집 규모**: 총 **{total}건** 수집 (뉴스 {news_count} · 블로그 {blog_count})\n"
    brief += (
        f"- 🧩 **이슈 압축**: 유사·중복 기사를 묶으면 실제 핵심 이슈는 **{unique_count}개**"
        f" (중복성 기사 {dup_count}건 정리됨)\n"
    )
    brief += f"- 🗓️ **실제 보도 기간**: {period_txt}\n"

    if not cluster_df.empty:
        brief += "- 🔥 **가장 많이 다뤄진 이슈 TOP 3**\n"
        top3 = cluster_df.head(3)
        for i, (_, row) in enumerate(top3.iterrows(), start=1):
            brief += (
                f"    {i}. \"{row['대표 제목']}\" "
                f"— 관련 기사 **{row['관련 기사 수']}건** ({row['구분']})\n"
            )

        # 집중 보도된 대형 이슈(관련 2건 이상) 개수 안내
        big_issues = int((cluster_df["관련 기사 수"] >= 2).sum())
        if big_issues > 0:
            brief += (
                f"- 📌 **집중 보도 이슈**: 관련 기사 2건 이상으로 묶인 화제성 이슈가 "
                f"총 **{big_issues}개** 포착되었습니다.\n"
            )

    return brief


# 7. 실행 버튼 및 화면 레이아웃
if st.button("📊 수집 및 요약 시작"):
    if not st.session_state.api_authenticated:
        st.warning("⚠️ 화면 상단에서 네이버 API 인증키를 먼저 등록해 주세요.")
    elif not selected_brands:
        st.warning("동향을 파악할 브랜드를 선택해 주세요.")
    else:
        all_dfs = []
        with st.spinner("경쟁사 미디어 동향을 실시간 수집 및 유사 이슈 묶는 중입니다..."):
            for brand in selected_brands:
                if "뉴스" in channels:
                    df_news = fetch_naver_data(brand, "news", start_date, start_date if start_date > end_date else end_date)
                    if df_news is not None and not df_news.empty:
                        all_dfs.append(df_news)
                if "블로그" in channels:
                    df_blog = fetch_naver_data(brand, "blog", start_date, start_date if start_date > end_date else end_date)
                    if df_blog is not None and not df_blog.empty:
                        all_dfs.append(df_blog)
            
            if all_dfs:
                raw_df = pd.concat(all_dfs, ignore_index=True)

                # 브랜드별 이슈 클러스터 테이블을 미리 계산해 재사용
                brand_clusters = {
                    brand: build_cluster_table(
                        raw_df[raw_df["브랜드"] == brand], cluster_threshold
                    )
                    for brand in selected_brands
                }

                total_raw = len(raw_df)
                total_issues = sum(len(t) for t in brand_clusters.values())
                st.success(
                    f"설정 기간({start_date} ~ {end_date}) 동안 총 **{total_raw}건**을 수집했고, "
                    f"유사 기사를 묶어 **{total_issues}개 핵심 이슈**로 압축했습니다!"
                )
                
                # [섹션 1] 브랜드 브리핑
                st.header("🎯 브랜드별 전체 동향 브리핑")
                cols = st.columns(2)
                for i, brand in enumerate(selected_brands):
                    brand_df = raw_df[raw_df["브랜드"] == brand]
                    cluster_df = brand_clusters[brand]
                    col_idx = i % 2
                    with cols[col_idx]:
                        with st.container(border=True):
                            briefing_text = generate_brand_briefing(brand, brand_df, cluster_df)
                            st.markdown(briefing_text)
                            
                st.markdown("---")
                
                # [섹션 2] 이슈별 대표 기사 (중복 묶음)
                st.header("📋 이슈별 대표 기사 목록 (중복 기사 묶음)")
                st.caption("같은 사건을 다룬 유사 기사는 하나의 이슈로 묶었습니다. '관련 기사 수'가 많을수록 화제성이 큰 이슈입니다.")
                tabs = st.tabs(selected_brands)
                for i, brand in enumerate(selected_brands):
                    with tabs[i]:
                        cluster_df = brand_clusters[brand]
                        if cluster_df.empty:
                            st.info("선택하신 기간 내 수집된 세부 결과가 없습니다.")
                        else:
                            display_cols = ["관련 기사 수", "구분", "대표 제목", "요약본", "대표 링크", "게시일"]
                            st.dataframe(
                                cluster_df[display_cols],
                                column_config={
                                    "관련 기사 수": st.column_config.NumberColumn(
                                        "관련 기사 수", format="%d건", help="이 이슈로 묶인 유사 기사 총 개수"
                                    ),
                                    "대표 링크": st.column_config.LinkColumn("대표 기사 보기"),
                                },
                                use_container_width=True,
                                hide_index=True
                            )
            else:
                st.warning("선택하신 기간 내에 발행된 관련 기사나 포스팅이 존재하지 않습니다. 검색 기간을 늘려보세요!")
