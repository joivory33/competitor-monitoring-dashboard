import streamlit as st
import pandas as pd
import requests
import datetime
import email.utils

# 1. 페이지 설정
st.set_page_config(
    page_title="경쟁사 마켓 트렌드 모니터링",
    page_icon="📰",
    layout="wide"
)

st.title("📰 경쟁사 뉴스 및 블로그 모니터링 요약")
st.markdown("설정한 기간 동안 **여기어때, 트립닷컴, 에어비앤비, 모두투어, 클룩, NOL** 관련 핵심 동향을 분석합니다.")

# 2. 사이드바 구성
st.sidebar.header("🔍 설정 필터")

today = datetime.date.today()
start_date = st.sidebar.date_input("시작일", today - datetime.timedelta(days=7))
end_date = st.sidebar.date_input("종료일", today)

brands = ["여기어때", "트립닷컴", "에어비앤비", "모두투어", "클룩", "놀(NOL)"]
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

st.sidebar.subheader("🔑 네이버 API 인증키 입력")
client_id = st.sidebar.text_input("Naver Client ID", type="password", help="네이버 개발자 센터에서 발급받은 Client ID를 입력하세요.")
client_secret = st.sidebar.text_input("Naver Client Secret", type="password", help="네이버 개발자 센터에서 발급받은 Client Secret을 입력하세요.")


# 3. 네이버 날짜 데이터 규격 분석 및 파싱 함수 (기간 필터링용)
def parse_naver_date(date_str, item_type):
    """뉴스(RFC 822) 및 블로그(YYYYMMDD)의 발행일을 파이썬 날짜 객체로 변환합니다."""
    if not date_str:
        return None
    try:
        if item_type == "news":
            # 예시: "Thu, 20 Aug 2026 10:24:00 +0900"
            parsed_dt = email.utils.parsedate_to_datetime(date_str)
            return parsed_dt.date()
        elif item_type == "blog":
            # 예시: "20260820"
            return datetime.datetime.strptime(str(date_str).strip(), "%Y%m%d").date()
    except Exception:
        return None


# 4. 텍스트 유사도 비교 함수 (80% 중복 제거 알고리즘)
def get_char_ngrams(text, n=2):
    clean_text = "".join(text.split())
    return set(clean_text[i:i+n] for i in range(len(clean_text) - n + 1))


def is_too_similar(title1, title2, threshold=0.75):
    if not title1 or not title2:
        return False
    set1 = get_char_ngrams(title1)
    set2 = get_char_ngrams(title2)
    union = len(set1.union(set2))
    if union == 0:
        return False
    similarity = len(set1.intersection(set2)) / union
    return similarity >= threshold


def filter_duplicates(df, threshold=0.75):
    if df.empty:
        return df
    
    keep_indices = []
    for brand, group in df.groupby("브랜드"):
        processed_titles = []
        for idx, row in group.iterrows():
            current_title = row["제목"]
            is_dup = False
            for past_title in processed_titles:
                if is_too_similar(current_title, past_title, threshold):
                    is_dup = True
                    break
            if not is_dup:
                keep_indices.append(idx)
                processed_titles.append(current_title)
                
    return df.loc[keep_indices].reset_index(drop=True)


# 5. 데이터 수집 함수 (기간 필터 완벽 보완)
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
        "display": 100,  # 기간 내 기사를 최대한 많이 발굴하기 위해 최대 한도로 수집
        "sort": "date"   # 최신순 정렬을 통해 대상 기간 기사가 누락 없이 걸려들게 합니다.
    }
    
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
                
                # 날짜 정보 판별 및 파싱
                raw_pub_date = item.get('pubDate') if search_type == "news" else item.get('postdate')
                parsed_date = parse_naver_date(raw_pub_date, search_type)
                
                # 🎯 [핵심 보완] 사용자가 설정한 시작일과 종료일 범위 내에 있는 글만 엄격하게 수집합니다.
                if parsed_date:
                    if not (start_dt <= parsed_date <= end_dt):
                        continue  # 기간 밖의 글은 저장하지 않고 건너뜁니다.
                
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


# 6. 브랜드별 전체 활동 요약 자동 생성기
def generate_brand_briefing(brand, df_brand):
    if df_brand.empty:
        return "선택하신 기간 내 수집된 활동 데이터가 없습니다."
        
    news_count = len(df_brand[df_brand["구분"] == "뉴스"])
    blog_count = len(df_brand[df_brand["구분"] == "블로그"])
    
    brief = f"**📢 {brand} 동향 브리핑**\n"
    brief += f"- 이번 기간 동안 총 **{len(df_brand)}건**의 유의미한 콘텐츠(뉴스 {news_count}건, 블로그 {blog_count}건)가 수집되었습니다.\n"
    
    if news_count > 0:
        top_news = df_brand[df_brand["구분"] == "뉴스"].iloc[0]["제목"]
        brief += f"- **주요 마케팅/비즈니스 이슈**: \"{top_news}\" 등을 중심으로 주요 미디어 노출이 발생했습니다.\n"
    if blog_count > 0:
        top_blog = df_brand[df_brand["구분"] == "블로그"].iloc[0]["제목"]
        brief += f"- **소비자 반응 및 바이럴**: 블로그 채널에서는 \"{top_blog}\" 콘텐츠가 주목을 받았습니다.\n"
        
    return brief


# 7. 실행 버튼 및 화면 레이아웃
if st.button("📊 수집 및 요약 시작"):
    if not selected_brands:
        st.warning("동향을 파악할 브랜드를 선택해 주세요.")
    else:
        if not client_id or not client_secret:
            # 💡 [친절한 안내문 업데이트] API 키 미입력 상태 시 아래 안내 박스가 노출됩니다.
            st.info("💡 실시간 데이터 수집을 시작하려면 **왼쪽 사이드바**에 API 인증키를 입력해야 합니다.")
        else:
            all_dfs = []
            with st.spinner("경쟁사 미디어 동향을 실시간 수집 및 중복 정제 중입니다..."):
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
                    raw_count = len(raw_df)
                    
                    # 중복 정제 실행 (기준값: 75% 유사도)
                    final_df = filter_duplicates(raw_df, threshold=0.75)
                    filtered_count = len(final_df)
                    st.success(f"설정 기간({start_date} ~ {end_date}) 동안 총 {raw_count}건의 기사 중 중복을 완벽 필터링하고 **최종 {filtered_count}건**의 엄선된 데이터만 추출했습니다!")
                    
                    # -----------------------------------------------------------------
                    # [섹션 1] 한눈에 보는 브랜드별 전체 요약본
                    # -----------------------------------------------------------------
                    st.header("🎯 브랜드별 전체 동향 브리핑")
                    st.markdown("수집된 방대한 콘텐츠를 마케팅 분석 관점에서 압축하여 보여줍니다.")
                    
                    cols = st.columns(2)
                    for i, brand in enumerate(selected_brands):
                        brand_df = final_df[final_df["브랜드"] == brand]
                        col_idx = i % 2
                        with cols[col_idx]:
                            with st.container(border=True):
                                briefing_text = generate_brand_briefing(brand, brand_df)
                                st.markdown(briefing_text)
                                
                    st.markdown("---")
                    
                    # -----------------------------------------------------------------
                    # [섹션 2] 브랜드별 상세 내용 및 원문 링크 표 (탭 구조)
                    # -----------------------------------------------------------------
                    st.header("📋 세부 원문 목록 및 상세 요약")
                    st.markdown("원하는 브랜드를 탭으로 선택해 상세 요약본과 원문 링크를 직접 확인하실 수 있습니다.")
                    
                    tabs = st.tabs(selected_brands)
                    for i, brand in enumerate(selected_brands):
                        with tabs[i]:
                            brand_df = final_df[final_df["브랜드"] == brand]
                            if brand_df.empty:
                                st.info("선택하신 기간 내 수집된 세부 결과가 없습니다.")
                            else:
                                display_cols = ["구분", "제목", "요약본", "원문 링크", "게시일"]
                                st.dataframe(
                                    brand_df[display_cols],
                                    column_config={
                                        "원문 링크": st.column_config.LinkColumn("원문 보러가기")
                                    },
                                    use_container_width=True,
                                    hide_index=True
                                )
                else:
                    st.warning("선택하신 기간 내에 발행된 관련 기사나 포스팅이 존재하지 않습니다. 검색 기간을 늘려보세요!")


# -----------------------------------------------------------------
# 💡 [친절한 이용 안내 가이드] 대시보드 하단에 상시 배치되는 가이드 카드
# -----------------------------------------------------------------
st.markdown("---")
with st.expander("🔑 3분 만에 무료로 '네이버 검색 API 인증키' 발급받는 방법 안내", expanded=True):
    st.markdown("""
    이 대시보드는 네이버 검색 서버와 안전하게 통신하기 위해 사용자 개별 **API 출입키**를 활용합니다. 아래 절차대로 접속하셔서 무료 키를 발급받아 입력해 주세요!
    
    1. **[네이버 개발자 센터 공식 링크](https://developers.naver.com/main/)** 주소로 접속합니다.
    2. 소지하고 계신 개인 네이버 아이디로 **로그인**을 진행합니다.
    3. 상단 메뉴에서 **`Application (애플리케이션)`** ➡️ **`내 애플리케이션`** 메뉴로 진입합니다.
    4. **`애플리케이션 등록`** 버튼을 누른 후 아래 정보를 입력합니다:
       * **애플리케이션 이름**: `마켓 모니터링 대시보드` (자유롭게 입력 가능)
       * **사용 API**: 검색창에서 **`검색`**을 선택하고 추가합니다.
       * **로그인 오픈 API 서비스 환경**: **`웹 설정`**을 선택하고, 주소창에 현재 보고 계신 본인의 스트림릿 대시보드 주소를 복사해 입력합니다.
    5. 최종 등록을 완료하시면 **`Client ID`**와 **`Client Secret`** 키가 화면에 나타납니다!
    6. 이 발급받은 두 가지 키를 왼쪽 사이드바의 입력 칸에 각각 복사해서 넣으신 뒤, **[📊 수집 및 요약 시작]** 버튼을 누르시면 됩니다.
    
    ※ 한 번 입력한 API 키는 웹브라우저 창을 완전히 닫기 전까지 메모리에 안전하게 임시 보존되므로 연속 사용 시 편리합니다.
    """)
