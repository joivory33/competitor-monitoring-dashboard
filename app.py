import streamlit as st
import pandas as pd
import requests
import datetime
import email.utils
import base64
import re
import json

# 1. 페이지 설정
st.set_page_config(page_title="경쟁사 마켓 트렌드 모니터링", page_icon="📰", layout="wide")

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
# 🔑 [자동 저장] URL 파라미터에서 저장된 API 키 복구
# -----------------------------------------------------------------
def encode_key(val):
    return base64.b64encode(val.encode()).decode() if val else ""

def decode_key(val):
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
# 2. 사이드바
# -----------------------------------------------------------------
st.sidebar.header("🔍 설정 필터")
today = datetime.date.today()

st.sidebar.markdown("**🗓️ 시작 일시**")
c1, c2 = st.sidebar.columns([3, 2])
start_date = c1.date_input("시작일", today - datetime.timedelta(days=7), label_visibility="collapsed")
start_time = c2.time_input("시작 시각", datetime.time(0, 0), label_visibility="collapsed")

st.sidebar.markdown("**🗓️ 종료 일시**")
c3, c4 = st.sidebar.columns([3, 2])
end_date = c3.date_input("종료일", today, label_visibility="collapsed")
end_time = c4.time_input("종료 시각", datetime.time(23, 59), label_visibility="collapsed")

start_dt_full = datetime.datetime.combine(start_date, start_time)
end_dt_full = datetime.datetime.combine(end_date, end_time)
if start_dt_full > end_dt_full:
    start_dt_full, end_dt_full = end_dt_full, start_dt_full

st.sidebar.caption(f"⏱️ 수집 범위: {start_dt_full:%Y-%m-%d %H:%M} ~ {end_dt_full:%Y-%m-%d %H:%M}")
st.sidebar.caption("※ 블로그는 네이버가 날짜만 제공하여 날짜 단위로 필터됩니다.")
st.sidebar.markdown("---")

brands = ["하나투어", "여기어때", "트립닷컴", "에어비앤비", "모두투어", "클룩", "놀(NOL)"]
selected_brands = st.sidebar.multiselect("모니터링 대상 브랜드", options=brands, default=brands)
channels = st.sidebar.multiselect("수집 채널", options=["뉴스", "블로그"], default=["뉴스", "블로그"])

cluster_threshold = st.sidebar.slider(
    "🧩 중복 기사 묶기 민감도", min_value=0.10, max_value=0.60, value=0.20, step=0.01,
    help="값이 낮을수록 비슷한 주제의 기사를 더 넓게 하나로 묶습니다."
)

# 💡 [신규] AI 정밀 인사이트(Gemini) 토글
st.sidebar.markdown("---")
use_gemini = st.sidebar.toggle("🤖 AI 정밀 인사이트(Gemini)", value=False,
                               help="켜면 Gemini가 기사 내용을 읽고 인사이트/감성을 재생성합니다. (키 필요)")
gemini_key, gemini_model = "", "gemini-2.5-flash"
if use_gemini:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password",
                                       value=st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else "")
    gemini_model = st.sidebar.text_input("모델명", value="gemini-2.5-flash",
                                         help="본인이 쓰던 작동 모델명으로 맞춰주세요.")

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 네이버 API 발급 가이드")
with st.sidebar.expander("📍 [필독] 1분 API 발급 가이드", expanded=True):
    st.markdown("""
    ### 1️⃣ 애플리케이션 등록 및 API 선택
    * **이름:** `검색 키워드` 입력
    * **사용 API:** 목록에서 **[네이버 로그인]** 선택

    ### 2️⃣ 제공 정보 설정
    * **회원이름, 성별, 출생연도**만 필수/추가로 체크 (나머지는 모두 체크 해제)

    ### 3️⃣ 서비스 환경 설정 (PC 웹)
    * **환경 추가:** **[PC 웹]** 선택 후 등록
    * **서비스 URL 및 Callback URL:**
    ```text
    https://instagram-insight-dashboard-yfksdz8sudm8rqyrxy3cqz.streamlit.app/
    ```
    """)

client_id = st.session_state.naver_client_id
client_secret = st.session_state.naver_client_secret


# -----------------------------------------------------------------
# 3. 날짜/시간 파싱
# -----------------------------------------------------------------
def parse_naver_datetime(date_str, item_type):
    if not date_str:
        return None
    try:
        if item_type == "news":
            return email.utils.parsedate_to_datetime(date_str).replace(tzinfo=None)
        elif item_type == "blog":
            return datetime.datetime.strptime(str(date_str).strip(), "%Y%m%d")
    except Exception:
        return None

def in_period(dt, item_type, start_dt, end_dt):
    if dt is None:
        return True
    if item_type == "blog":
        return start_dt.date() <= dt.date() <= end_dt.date()
    return start_dt <= dt <= end_dt


# -----------------------------------------------------------------
# 4. 유사 이슈 클러스터링 (하이브리드)
# -----------------------------------------------------------------
STOPWORDS = {"대표","신임","출범","전환","발표","공개","진행","기념","선포","체제","회사","기업","관련","위해","통해","이번","지난","오는","역시"}

def extract_keywords(text):
    t = text.lower().replace("chapter", "챕터").replace("號", "")
    t = re.sub(r"[^0-9a-z가-힣]+", " ", t)
    words = set()
    for w in t.split():
        if not w or w in STOPWORDS:
            continue
        if re.fullmatch(r"[가-힣]", w):
            continue
        words.add(w)
    return words

def get_char_ngrams(text, n=2):
    clean = "".join(text.split())
    return set(clean[i:i + n] for i in range(len(clean) - n + 1))

def hybrid_similarity(t1, t2):
    if not t1 or not t2:
        return 0.0
    k1, k2 = extract_keywords(t1), extract_keywords(t2)
    ku = len(k1 | k2)
    word_sim = len(k1 & k2) / ku if ku else 0.0
    c1, c2 = get_char_ngrams(t1), get_char_ngrams(t2)
    cu = len(c1 | c2)
    char_sim = len(c1 & c2) / cu if cu else 0.0
    return max(word_sim, char_sim)


# -----------------------------------------------------------------
# 4-1. 감성 3분류 (부정 우선 → 순수 사실 기타 → 나머지 긍정)
# -----------------------------------------------------------------
POSITIVE_WORDS = {"출시","확대","성장","최대","흑자","호평","인기","급증","돌파","협약","제휴","투자","유치","개선","회복","상승","증가","호실적","흥행","완판","매진","강화","선정","우수","혁신","기대","도약","승부수","시동","역대급","신기록","달성","공략","선도","최고","호조","출범","선포","본격화","청사진","전략","고도화","선점","희망","가치","상생","동행","기부","후원","체결","맞손","손잡","론칭","오픈","확장","프리미엄","정조준","띄운","밸류업"}
NEGATIVE_WORDS = {"논란","소송","하락","감소","적자","부진","사고","피해","불만","항의","취소","지연","결함","리콜","벌금","과징금","제재","위기","우려","갑질","먹통","오류","해킹","유출","실패","급감","손실","파업","논쟁","비판","역풍","철수","축소","경고","구설","위반","폐지","충돌","악화","타격","공백","삐걱","수상한","허리띠","퇴사","적발","의혹","도마","추락","뭇매","몸살","한파","반발"}
FACTUAL_PATTERNS = [r"증시\s*일정", r"오늘의\s*증시", r"코스닥", r"유가증권", r"환율", r"부고", r"프롤로그", r"후기", r"여행기", r"다녀온", r"다녀왔", r"에어텔", r"\d\s*박\s*\d\s*일", r"패키지\s*추천", r"여행\s*일정", r"일정\s*및", r"면세점\s*쇼핑"]

def classify_3way(title, desc):
    text = f"{title} {desc}".lower()
    if any(w.lower() in text for w in NEGATIVE_WORDS):
        return "부정"
    if any(re.search(p, text) for p in FACTUAL_PATTERNS):
        return "기타"
    return "긍정"


# -----------------------------------------------------------------
# 4-2. 인사이트 문장 생성 (규칙 기반: 요약본에서 핵심 리드 추출)
# -----------------------------------------------------------------
def make_insight(title, desc):
    d = re.sub(r"<[^>]+>", "", desc or "").replace("&quot;", '"').strip()
    d = re.sub(r"^사진\s*=\s*\S+\s*(제공)?\s*", "", d)
    d = re.sub(r"^[가-힣]{2,4}\s*[가-힣]*\s*기자\s*[=|:]\s*", "", d)
    d = re.sub(r"^$[^$]{1,20}$\s*", "", d)
    d = re.sub(r"\s+", " ", d).strip()
    if not d:
        return re.sub(r"\s+", " ", re.sub(r"^$[^$]{1,20}$\s*", "", title)).strip()
    m = re.search(r"^(.{15,90}?(?:다|음|함|됨|한다|된다|밝혔다|했다|계획|예정))[\.\s]", d + " ")
    insight = m.group(1) if m else d[:80]
    return insight.strip().rstrip(".") + "."


# -----------------------------------------------------------------
# 4-3. [옵션] Gemini 정밀 인사이트/감성 (브랜드별 배치 1회 호출)
# -----------------------------------------------------------------
def gemini_enrich(brand, clusters, api_key, model):
    """clusters의 대표 제목+요약본을 배치로 보내 인사이트/감성을 재생성."""
    if not api_key or not clusters:
        return clusters
    listing = "\n".join(
        f'{i}. 제목: {c["rep"]["제목"]} / 요약: {c["rep"]["요약본"][:150]}'
        for i, c in enumerate(clusters)
    )
    prompt = (
        f"다음은 '{brand}' 관련 뉴스/블로그 이슈 목록이다. 각 항목을 분석해 "
        f"(1) insight: 기사 내용을 파악한 한 문장(40자 내외) 핵심 인사이트, "
        f"(2) sentiment: '긍정'/'부정'/'기타' 중 하나(견해 없는 순수 사실정보만 '기타', 부정 요소 있으면 '부정', 그 외 '긍정')를 매겨라. "
        f'반드시 아래 JSON 배열로만 답하라: [{{"idx":0,"insight":"...","sentiment":"긍정"}}]\n\n{listing}'
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        if r.status_code != 200:
            st.warning(f"[{brand}] Gemini 응답 오류({r.status_code}) → 규칙 기반으로 대체합니다.")
            return clusters
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.MULTILINE).strip()
        arr = json.loads(txt)
        by_idx = {int(o["idx"]): o for o in arr if "idx" in o}
        for i, c in enumerate(clusters):
            if i in by_idx:
                o = by_idx[i]
                if o.get("insight"):
                    c["insight"] = o["insight"].strip()
                if o.get("sentiment") in ("긍정", "부정", "기타"):
                    c["sentiment"] = o["sentiment"]
    except Exception as e:
        st.warning(f"[{brand}] Gemini 처리 실패({e}) → 규칙 기반으로 대체합니다.")
    return clusters


def build_clusters(df_brand, threshold):
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
        c["sentiment"] = classify_3way(c["rep"]["제목"], c["rep"]["요약본"])
        c["insight"] = make_insight(c["rep"]["제목"], c["rep"]["요약본"])
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def clusters_to_table(clusters):
    rows = []
    for c in clusters:
        rep = c["rep"]
        rows.append({
            "관련 기사 수": c["count"],
            "핵심 인사이트": c["insight"],
            "구분": rep["구분"],
            "대표 제목": rep["제목"],
            "대표 링크": rep["원문 링크"],
            "게시일시": rep["게시표시"],
        })
    return pd.DataFrame(rows)


# 5. 데이터 수집
def fetch_naver_data(query, search_type, start_dt, end_dt):
    if not client_id or not client_secret:
        return None
    url = f"https://openapi.naver.com/v1/search/{search_type}.json"
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    params = {"query": query, "display": 100, "sort": "sim"}
    clean_query = query.split("(")[0].strip()
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get("items", [])
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
                raw = item.get('pubDate') if search_type == "news" else item.get('postdate')
                dt = parse_naver_datetime(raw, search_type)
                if not in_period(dt, search_type, start_dt, end_dt):
                    continue
                if dt is None:
                    disp = str(raw)
                elif search_type == "news":
                    disp = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    disp = dt.strftime("%Y-%m-%d")
                data_list.append({
                    "브랜드": query, "구분": "뉴스" if search_type == "news" else "블로그",
                    "제목": title, "요약본": description, "원문 링크": link,
                    "게시일시": dt, "게시표시": disp
                })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 오류 ({query}): {e}")
    return None


# -----------------------------------------------------------------
# 6. 긍정/부정/기타 3단 분리 브리핑 (한 소재당 한 줄, 인사이트 기반)
# -----------------------------------------------------------------
def generate_brand_briefing(brand, df_brand, clusters):
    if df_brand.empty:
        return "선택하신 기간 내 수집된 활동 데이터가 없습니다."
    total = len(df_brand)
    news_count = int((df_brand["구분"] == "뉴스").sum())
    blog_count = int((df_brand["구분"] == "블로그").sum())
    unique_count = len(clusters)
    dup_count = total - unique_count
    valid = [d for d in df_brand["게시일시"] if isinstance(d, datetime.datetime)]
    period_txt = f"{min(valid):%Y-%m-%d %H:%M} ~ {max(valid):%Y-%m-%d %H:%M}" if valid else "기간 정보 없음"

    md = f"### 📢 {brand} 동향 브리핑\n"
    md += f"- 📊 **수집 규모**: 총 **{total}건** (뉴스 {news_count} · 블로그 {blog_count})\n"
    md += f"- 🧩 **이슈 압축**: 유사·중복을 묶어 실제 핵심 이슈 **{unique_count}개** (중복성 기사 {dup_count}건 정리)\n"
    md += f"- 🗓️ **실제 보도 기간**: {period_txt}\n"

    pos = [c for c in clusters if c["sentiment"] == "긍정"]
    neg = [c for c in clusters if c["sentiment"] == "부정"]
    etc = [c for c in clusters if c["sentiment"] == "기타"]

    def block(icon, label, items):
        s = f"\n**{icon} {label} ({len(items)}건)**\n\n"
        if not items:
            return s + "- 해당 없음\n"
        return s + "\n".join(f"- {c['insight']} `관련 {c['count']}건`" for c in items) + "\n"

    md += block("🟢", "긍정적 이슈", pos)
    md += block("🔴", "부정적 이슈", neg)
    md += block("⚪", "기타(사실 정보성) 이슈", etc)
    return md


# 7. 실행
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
                brand_clusters = {}
                for brand in selected_brands:
                    cl = build_clusters(raw_df[raw_df["브랜드"] == brand], cluster_threshold)
                    if use_gemini and gemini_key and cl:
                        cl = gemini_enrich(brand, cl, gemini_key, gemini_model)
                        cl.sort(key=lambda c: c["count"], reverse=True)
                    brand_clusters[brand] = cl

                total_raw = len(raw_df)
                total_issues = sum(len(cl) for cl in brand_clusters.values())
                st.success(
                    f"설정 기간({start_dt_full:%Y-%m-%d %H:%M} ~ {end_dt_full:%Y-%m-%d %H:%M}) 동안 "
                    f"총 **{total_raw}건**을 수집했고, 유사 기사를 묶어 **{total_issues}개 핵심 이슈**로 압축했습니다!"
                )

                # [섹션 1] 브리핑
                st.header("🎯 브랜드별 전체 동향 브리핑 (긍정/부정/기타)")
                cols = st.columns(2)
                for i, brand in enumerate(selected_brands):
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.markdown(generate_brand_briefing(brand, raw_df[raw_df["브랜드"] == brand], brand_clusters[brand]))

                st.markdown("---")

                # [섹션 2] 이슈별 대표 기사 목록 (브랜드 → 긍정/부정/기타 분리)
                st.header("📋 이슈별 대표 기사 목록 (긍정 / 부정 / 기타)")
                st.caption("같은 사건을 다룬 유사 기사는 하나의 이슈로 묶었습니다. 감성 탭별로 나눠 보고, '펼쳐보기'로 묶인 개별 기사 전체를 볼 수 있습니다.")
                senti_meta = [("🟢 긍정", "긍정"), ("🔴 부정", "부정"), ("⚪ 기타", "기타")]

                tabs = st.tabs(selected_brands)
                for bi, brand in enumerate(selected_brands):
                    with tabs[bi]:
                        clusters = brand_clusters[brand]
                        if not clusters:
                            st.info("선택하신 기간 내 수집된 세부 결과가 없습니다.")
                            continue
                        senti_tabs = st.tabs([f"{lbl} ({sum(1 for c in clusters if c['sentiment']==key)})" for lbl, key in senti_meta])
                        for si, (lbl, key) in enumerate(senti_meta):
                            with senti_tabs[si]:
                                sub = [c for c in clusters if c["sentiment"] == key]
                                if not sub:
                                    st.info("해당 감성으로 분류된 이슈가 없습니다.")
                                    continue
                                table = clusters_to_table(sub)
                                st.dataframe(
                                    table[["관련 기사 수", "핵심 인사이트", "구분", "대표 제목", "대표 링크", "게시일시"]],
                                    column_config={
                                        "관련 기사 수": st.column_config.NumberColumn("관련 기사 수", format="%d건"),
                                        "대표 링크": st.column_config.LinkColumn("대표 기사 보기"),
                                    },
                                    use_container_width=True, hide_index=True
                                )
                                st.markdown("###### 🔎 이슈별 개별 기사 전체 펼쳐보기")
                                for c in sub:
                                    with st.expander(f"[{c['count']}건] {c['rep']['제목']}"):
                                        member_df = pd.DataFrame([{
                                            "구분": m["구분"], "제목": m["제목"], "요약본": m["요약본"],
                                            "원문 링크": m["원문 링크"], "게시일시": m["게시표시"],
                                        } for m in c["members"]])
                                        st.dataframe(
                                            member_df,
                                            column_config={"원문 링크": st.column_config.LinkColumn("원문 보러가기")},
                                            use_container_width=True, hide_index=True
                                        )
            else:
                st.warning("선택하신 기간 내에 발행된 관련 기사나 포스팅이 존재하지 않습니다. 검색 기간을 늘려보세요!")
