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
client_id = st.sidebar.text_input("Naver Client ID", type="password")
client_secret = st.sidebar.text_input("Naver Client Secret", type="password")


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


# 4. 텍스트 유사도 비교 함수 (75% 중복 제거)
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


# 5. 데이터 수집 및 정제 함수 (수정 완료!)
def fetch_naver_data(query, search_type, start_dt, end_dt):
    if not client_id or not client_secret:
        return None
        
    url = f"https://openapi.naver.com/v1/search/{search_type}.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    # 🎯 [수정 1] 정렬을 다시 정확도순('sim')으로 변경하여 스팸 게시글을 원천 배제합니다.
    params = {
        "query": query,
        "display": 100,
        "sort": "sim"
    }
    
    # 키워드 필터용 타겟 단어 설정
    clean_query = query.split("(")[0].strip() # "놀(NOL)" -> "놀" 또는 "NOL" 검사용
    
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
                
                # 🎯 [수정 2] 본문이나 제목에 진짜 브랜드명이 들어있는지 교차 검증 (무관한 일상 글 배제)
                text_to_check = (title + " " + description).lower()
                
                # '놀(NOL)'의 경우 일상어 '놀다' 등과 구분하기 위해 브랜드 고유 키워드 체크
                if query == "놀(NOL)":
                    if "놀 카드" not in text_to_check and "nol 카드" not in text_to_check and "야놀자" not in text_to_check:
                        continue
                else:
                    if clean_query.lower() not in text_to_check:
                        continue
                
                # 날짜 파싱 및 사용자가 설정한 기간 범위 체크
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


# 6. 브랜드별 요약 브리핑 생성기
def generate_brand_briefing(brand, df_brand):
    if df_brand.empty:
        return "선택하신 기간 내 수집된 활동 데이터가 없습니다."
        
    news_count = len(df_brand[df_brand["구분"] == "뉴스"])
    blog_count = len(df_brand[df_brand["구분"] == "블로그"])
    
    brief = f"**📢 {brand} 동향 브리핑**\n"
    brief += f"- 이번 기간 동안 총 **{len(df_brand)}건**의 유의미한 콘텐츠(뉴스 {news_count}건, 블로그 {blog_count}건)가 수집되었습니다.\n"
    
    if news_count > 0:
        top_news = df_brand[df_brand["구분"] == "뉴스"].iloc[0]["제목"]
        brief += f"- **주요 마케팅/비즈니스 이슈**: \"{top_news}\"\n"
    if blog_count > 0:
        top_blog = df_brand[df_brand["구분"] == "블로그"].iloc[0]["제목"]
        brief += f"- **소비자 반응 및 바이럴**: \"{top_blog}\"\n"
        
    return brief


# 7. 실행 버튼 및 화면 레이아웃
if st.button("📊 수집 및 요약 시작"):
    if not selected_brands:
        st.warning("동향을 파악할 브랜드를 선택해 주세요.")
    else:
        if not client_id or not client_secret:
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
                    
                    final_df = filter_duplicates(raw_df, threshold=0.75)
                    filtered_count = len(final_df)
                    st.success(f"설정 기간({start_date} ~ {end_date}) 동안 중복과 노이즈를 완벽 필터링하고 **최종 {filtered_count}건**의 관련성 높은 데이터를 추출했습니다!")
                    
                    # [섹션 1] 브랜드 브리핑
                    st.header("🎯 브랜드별 전체 동향 브리핑")
                    cols = st.columns(2)
                    for i, brand in enumerate(selected_brands):
                        brand_df = final_df[final_df["브랜드"] == brand]
                        col_idx = i % 2
                        with cols[col_idx]:
                            with st.container(border=True):
                                briefing_text = generate_brand_briefing(brand, brand_df)
                                st.markdown(briefing_text)
                                
                    st.markdown("---")
                    
                    # [섹션 2] 상세 원문 (탭 구조)
                    st.header("📋 세부 원문 목록 및 상세 요약")
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
# 🎯 [핵심만 남긴 심플 이용 안내 가이드]
# -----------------------------------------------------------------
st.markdown("---")
with st.container(border=True):
    st.markdown("""
    ### 🔑 네이버 API 인증키 발급 및 이용 안내
    본 대시보드는 네이버 실시간 검색 데이터를 안전하게 수집하기 위해 사용자 개인 API 인증키를 사용합니다.
    
    1. **[네이버 개발자 센터](https://developers.naver.com/main/)** 로그인 후 접속
    2. 상단 메뉴 **`Application` ➡️ `내 애플리케이션`** 이동
    3. **`애플리케이션 등록`** 진행
       - **사용 API**: `검색` 선택 후 추가
       - **로그인 오픈 API 서비스 환경**: `웹 설정` 선택 ➡️ 현재 사용 중인 대시보드 URL 주소 입력
    4. 발급 완료된 **`Client ID`**와 **`Client Secret`**을 왼쪽 사이드바에 복사하여 입력
    """)
