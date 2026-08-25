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

# 💡 [신규] 날짜 + 시간까지 정밀 지정
st.sidebar.markdown("**🗓️ 시작 일시**")
c1, c2 = st.sidebar.columns([3, 2])
start_date = c1.date_input("시작일", today - datetime.timedelta(days=7), label_visibility="collapsed")
start_time = c2.time_input("시작 시각", datetime.time(0, 0), label_visibility="collapsed")

st.sidebar.markdown("**🗓️ 종료 일시**")
c3, c4 = st.sidebar.columns([3, 2])
end_date = c3.date_input("종료일", today, label_visibility="collapsed")
end_time = c4.time_input("종료 시각", datetime.time(23, 59), label_visibility="collapsed")

# 날짜 + 시간을 하나의 datetime 범위로 결합
start_dt_full = datetime.datetime.combine(start_date, start_time)
end_dt_full = datetime.datetime.combine(end_date, end_time)
if start_dt_full > end_dt_full:  # 혹시 뒤집혀 있으면 자동 보정
    start_dt_full, end_dt_full = end_dt_full, start_dt_full

st.sidebar.caption(f"⏱️ 수집 범위: {start_dt_full:%Y-%m-%d %H:%M} ~ {end_dt_full:%Y-%m-%d %H:%M}")
st.sidebar.caption("※ 블로그는 네이버가 날짜만 제공하여 날짜 단위로 필터됩니다.")

st.sidebar.markdown("---")

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

# 💡 중복(유사 이슈) 묶기 민감도 조절 슬라이더 (기본값 0.2로 하향)
cluster_threshold = st.sidebar.slider(
    "🧩 중복 기사 묶기 민감도",
    min_value=0.10, max_value=0.60, value=0.20, step=0.01,
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


# -----------------------------------------------------------------
# 3. 네이버 날짜/시간 파싱 (뉴스: 시각까지 / 블로그: 날짜만)
# -----------------------------------------------------------------
def parse_naver_datetime(date_str, item_type):
    """뉴스는 시각까지 포함한 datetime, 블로그는 자정 datetime을 반환합니다."""
    if not date_str:
        return None
    try:
        if item_type == "news":
            parsed_dt = email.utils.parsedate_to_datetime(date_str)
            # KST(+0900) 벽시계 시각을 그대로 사용하기 위해 tz 정보만 제거
            return parsed_dt.replace(tzinfo=None)
        elif item_type == "blog":
            d = datetime.datetime.strptime(str(date_str).strip(), "%Y%m%d")
            return d  # 시각 정보 없음(자정)
    except Exception:
        return None


def in_period(dt, item_type, start_dt, end_dt):
    """뉴스는 시각까지, 블로그는 날짜 단위로 기간 포함 여부를 판정합니다."""
    if dt is None:
        return True  # 날짜 파싱 실패 시엔 일단 포함(누락 방지)
    if item_type == "blog":
        return start_dt.date() <= dt.date() <= end_dt.date()
    return start_dt <= dt <= end_dt


# -----------------------------------------------------------------
# 4. [핵심 로직] 유사 이슈 클러스터링 (하이브리드: 키워드 겹침 + 글자 유사도)
# -----------------------------------------------------------------
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
        if re.fullmatch(r"[가-힣]", w):
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
    k1, k2 = extract_keywords(title1), extract_keywords(title2)
    k_union = len(k1 | k2)
    word_sim = len(k1 & k2) / k_union if k_union else 0.0
    c1, c2 = get_char_ngrams(title1), get_char_ngrams(title2)
    c_union = len(c1 | c2)
    char_sim = len(c1 & c2) / c_union if c_union else 0.0
    return max(word_sim, char_sim)


# -----------------------------------------------------------------
# 4-1. [신규] 감성(긍정/부정/중립) 분류
# -----------------------------------------------------------------
POSITIVE_WORDS = {
    "출시", "확대", "성장", "최대", "흑자", "수상", "1위", "호평", "인기", "급증",
    "돌파", "협약", "제휴", "투자", "유치", "개선", "회복", "상승", "증가", "호실적",
    "흥행", "완판", "매진", "강화", "선정", "우수", "혁신", "기대", "도약", "승부수",
    "시동", "역대급", "신기록", "달성", "공략", "선도", "1등", "최고", "인상적", "호조"
}
NEGATIVE_WORDS = {
    "논란", "소송", "하락", "감소", "적자", "부진", "사고", "피해", "불만", "항의",
    "취소", "지연", "결함", "리콜", "벌금", "과징금", "제재", "위기", "우려", "갑질",
    "먹통", "오류", "해킹", "유출", "실패", "급감", "손실", "파업", "논쟁", "비판",
    "역풍", "철수", "축소", "경고", "구설", "위반", "폐지", "충돌", "악화", "타격"
}

def classify_sentiment(text):
    """텍스트의 긍/부정 키워드 수를 비교해 '긍정' / '부정' / '중립'을 반환합니다."""
    if not text:
        return "중립"
    t = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w.lower() in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w.lower() in t)
    if pos > neg:
        return "긍정"
    if neg > pos:
        return "부정"
    return "중립"


def build_clusters(df_brand, threshold):
    """브랜드 기사를 유사 이슈로 묶어 클러스터 리스트를 반환합니다.
    각 클러스터: {rep(대표행), members(list of row), count, sentiment}"""
    if df_brand.empty:
        return []

    clusters = []
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

    for c in clusters:
        c["count"] = len(c["members"])
        # 대표 기사(제목+요약)를 기준으로 감성 판정
        senti_text = f"{c['rep']['제목']} {c['rep']['요약본']}"
        c["sentiment"] = classify_sentiment(senti_text)

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def clusters_to_table(clusters):
    """클러스터 리스트를 요약 표(DataFrame)로 변환합니다."""
    rows = []
    for c in clusters:
        rep = c["rep"]
        rows.append({
            "관련 기사 수": c["count"],
            "감성": c["sentiment"],
            "구분": rep["구분"],
            "대표 제목": rep["제목"],
            "요약본": rep["요약본"],
            "대표 링크": rep["원문 링크"],
            "게시일시": rep["게시표시"],
        })
    return pd.DataFrame(rows)


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

                if query == "놀(NOL)":
                    if "놀 카드" not in text_to_check and "nol 카드" not in text_to_check and "야놀자" not in text_to_check:
                        continue
                else:
                    if clean_query.lower() not in text_to_check:
                        continue

                raw_pub_date = item.get('pubDate') if search_type == "news" else item.get('postdate')
                parsed_dt = parse_naver_datetime(raw_pub_date, search_type)

                # 🎯 날짜+시간 기준 기간 필터
                if not in_period(parsed_dt, search_type, start_dt, end_dt):
                    continue

                # 화면 표시용 게시일시 문자열
                if parsed_dt is None:
                    disp = str(raw_pub_date)
                elif search_type == "news":
                    disp = parsed_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    disp = parsed_dt.strftime("%Y-%m-%d")

                data_list.append({
                    "브랜드": query,
                    "구분": "뉴스" if search_type == "news" else "블로그",
                    "제목": title,
                    "요약본": description,
                    "원문 링크": link,
                    "게시일시": parsed_dt,
                    "게시표시": disp
                })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 오류 ({query}): {e}")
    return None


# -----------------------------------------------------------------
# 6. [개선] 긍정/부정/중립 3단 분리 동향 브리핑 생성기
# -----------------------------------------------------------------
def generate_brand_briefing(brand, df_brand, clusters):
    if df_brand.empty:
        return "선택하신 기간 내 수집된 활동 데이터가 없습니다."

    total = len(df_brand)
    news_count = int((df_brand["구분"] == "뉴스").sum())
    blog_count = int((df_brand["구분"] == "블로그").sum())
    unique_count = len(clusters)
    dup_count = total - unique_count

    # 실제 보도 기간(시각 포함)
    valid = [d for d in df_brand["게시일시"] if isinstance(d, datetime.datetime)]
    period_txt = f"{min(valid):%Y-%m-%d %H:%M} ~ {max(valid):%Y-%m-%d %H:%M}" if valid else "기간 정보 없음"

    brief = f"### 📢 {brand} 동향 브리핑\n"
    brief += f"- 📊 **수집 규모**: 총 **{total}건** (뉴스 {news_count} · 블로그 {blog_count})\n"
    brief += (
        f"- 🧩 **이슈 압축**: 유사·중복을 묶어 실제 핵심 이슈 **{unique_count}개** "
        f"(중복성 기사 {dup_count}건 정리)\n"
    )
    brief += f"- 🗓️ **실제 보도 기간**: {period_txt}\n"

    # 감성별로 소재(이슈) 분류
    pos = [c for c in clusters if c["sentiment"] == "긍정"]
    neg = [c for c in clusters if c["sentiment"] == "부정"]
    neu = [c for c in clusters if c["sentiment"] == "중립"]

    def line(c):
        # 소재 1개당 한 줄
        return f"    - \"{c['rep']['제목']}\" (관련 {c['count']}건)"

    brief += f"\n**🟢 긍정적 이슈 ({len(pos)}건)**\n"
    brief += "\n".join(line(c) for c in pos) + "\n" if pos else "    - 해당 없음\n"

    brief += f"\n**🔴 부정적 이슈 ({len(neg)}건)**\n"
    brief += "\n".join(line(c) for c in neg) + "\n" if neg else "    - 해당 없음\n"

    brief += f"\n**⚪ 중립·기타 이슈 ({len(neu)}건)**\n"
    brief += "\n".join(line(c) for c in neu) + "\n" if neu else "    - 해당 없음\n"

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
                    df_news = fetch_naver_data(brand, "news", start_dt_full, end_dt_full)
                    if df_news is not None and not df_news.empty:
                        all_dfs.append(df_news)
                if "블로그" in channels:
                    df_blog = fetch_naver_data(brand, "blog", start_dt_full, end_dt_full)
                    if df_blog is not None and not df_blog.empty:
                        all_dfs.append(df_blog)

            if all_dfs:
                raw_df = pd.concat(all_dfs, ignore_index=True)

                # 브랜드별 클러스터를 미리 계산해 재사용
                brand_clusters = {
                    brand: build_clusters(raw_df[raw_df["브랜드"] == brand], cluster_threshold)
                    for brand in selected_brands
                }

                total_raw = len(raw_df)
                total_issues = sum(len(cl) for cl in brand_clusters.values())
                st.success(
                    f"설정 기간({start_dt_full:%Y-%m-%d %H:%M} ~ {end_dt_full:%Y-%m-%d %H:%M}) 동안 "
                    f"총 **{total_raw}건**을 수집했고, 유사 기사를 묶어 "
                    f"**{total_issues}개 핵심 이슈**로 압축했습니다!"
                )

                # [섹션 1] 브랜드 브리핑
                st.header("🎯 브랜드별 전체 동향 브리핑 (긍정/부정 분리)")
                cols = st.columns(2)
                for i, brand in enumerate(selected_brands):
                    brand_df = raw_df[raw_df["브랜드"] == brand]
                    clusters = brand_clusters[brand]
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.markdown(generate_brand_briefing(brand, brand_df, clusters))

                st.markdown("---")

                # [섹션 2] 이슈별 대표 기사 + 개별 기사 펼쳐보기
                st.header("📋 이슈별 대표 기사 목록 (중복 기사 묶음)")
                st.caption("같은 사건을 다룬 유사 기사는 하나의 이슈로 묶었습니다. '관련 기사 수'가 많을수록 화제성이 큰 이슈이며, 아래 '펼쳐보기'로 묶인 개별 기사 전체를 볼 수 있습니다.")
                tabs = st.tabs(selected_brands)
                for i, brand in enumerate(selected_brands):
                    with tabs[i]:
                        clusters = brand_clusters[brand]
                        if not clusters:
                            st.info("선택하신 기간 내 수집된 세부 결과가 없습니다.")
                            continue

                        # (1) 이슈 요약 표
                        table = clusters_to_table(clusters)
                        display_cols = ["관련 기사 수", "감성", "구분", "대표 제목", "요약본", "대표 링크", "게시일시"]
                        st.dataframe(
                            table[display_cols],
                            column_config={
                                "관련 기사 수": st.column_config.NumberColumn("관련 기사 수", format="%d건"),
                                "대표 링크": st.column_config.LinkColumn("대표 기사 보기"),
                            },
                            use_container_width=True,
                            hide_index=True
                        )

                        # (2) 🔎 이슈별 개별 기사 전체 펼쳐보기
                        st.markdown("##### 🔎 이슈별 개별 기사 전체 펼쳐보기")
                        senti_icon = {"긍정": "🟢", "부정": "🔴", "중립": "⚪"}
                        for c in clusters:
                            rep = c["rep"]
                            icon = senti_icon.get(c["sentiment"], "⚪")
                            with st.expander(f"{icon} [{c['count']}건] {rep['제목']}"):
                                member_df = pd.DataFrame([{
                                    "구분": m["구분"],
                                    "제목": m["제목"],
                                    "요약본": m["요약본"],
                                    "원문 링크": m["원문 링크"],
                                    "게시일시": m["게시표시"],
                                } for m in c["members"]])
                                st.dataframe(
                                    member_df,
                                    column_config={
                                        "원문 링크": st.column_config.LinkColumn("원문 보러가기"),
                                    },
                                    use_container_width=True,
                                    hide_index=True
                                )
            else:
                st.warning("선택하신 기간 내에 발행된 관련 기사나 포스팅이 존재하지 않습니다. 검색 기간을 늘려보세요!")
