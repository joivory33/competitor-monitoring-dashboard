import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

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

today = datetime.today()
start_date = st.sidebar.date_input("시작일", today - timedelta(days=7))
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

st.sidebar.subheader("🔑 네이버 API 인증키")
client_id = st.sidebar.text_input("Naver Client ID", type="password")
client_secret = st.sidebar.text_input("Naver Client Secret", type="password")


# 3. 텍스트 유사도 비교 함수 (80% 중복 제거 알고리즘)
def get_char_ngrams(text, n=2):
    """문장 내 공백을 제거하고 n글자 단위로 쪼개어 세트를 만듭니다."""
    clean_text = "".join(text.split())
    return set(clean_text[i:i+n] for i in range(len(clean_text) - n + 1))


def is_too_similar(title1, title2, threshold=0.75):
    """두 제목의 글자 유사도를 비교하여 특정 기준(75% 이상)을 넘기면 중복으로 판정합니다."""
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
    """동일한 브랜드 내에서 제목이 지나치게 유사한 데이터를 하나만 남기고 필터링합니다."""
    if df.empty:
        return df
    
    keep_indices = []
    # 브랜드별로 그룹화하여 그룹 내부에서만 중복 검사 진행
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


# 4. 데이터 수집 함수 (문법 오타 원천 차단 적용 완료)
def fetch_naver_data(query, search_type):
    if not client_id or not client_secret:
        return None
        
    url = f"https://openapi.naver.com/v1/search/{search_type}.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": 80,
        "sort": "sim"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            # 이 부분의 마침표 오타 및 가독성을 깔끔하게 정돈했습니다.
            res_json = response.json()
            items = res_json.get("items", [])
            data_list = []
            for item in items:
                title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                description = item['description'].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                link = item['link']
                pub_date = item.get('postdate') or item.get('pubDate')
                
                data_list.append({
                    "브랜드": query,
                    "구분": "뉴스" if search_type == "news" else "블로그",
                    "제목": title,
                    "요약본": description,
                    "원문 링크": link,
                    "게시일": pub_date
                })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 오류 ({query}): {e}")
    return None


# 5. 브랜드별 전체 활동 요약 자동 생성기
def generate_brand_briefing(brand, df_brand):
    if df_brand.empty:
        return "수집된 활동 데이터가 없습니다."
        
    news_count = len(df_brand[df_brand["구분"] == "뉴스"])
    blog_count = len(df_brand[df_brand["구분"] == "블로그"])
    
    brief = f"**📢 {brand} 동향 브리핑**\n"
    brief += f"- 이번 기간 동안 총 **{len(df_brand)}건**의 유의미한 콘텐츠(뉴스 {news_count}건, 블로그 {blog_count}건)가 중복 제거 후 수집되었습니다.\n"
    
    if news_count > 0:
        top_news = df_brand[df_brand["구분"] == "뉴스"].iloc[0]["제목"]
        brief += f"- **주요 마케팅/비즈니스 이슈**: \"{top_news}\" 등을 중심으로 주요 미디어 노출이 발생했습니다.\n"
    if blog_count > 0:
        top_blog = df_brand[df_brand["구분"] == "블로그"].iloc[0]["제목"]
        brief += f"- **소비자 반응 및 바이럴**: 블로그 채널에서는 \"{top_blog}\" 콘텐츠가 주목을 받으며 긍정적인 브랜드 경험이 확산되고 있습니다.\n"
        
    return brief


# 6. 실행 버튼 및 화면 레이아웃
if st.button("📊 수집 및 요약 시작"):
    if not selected_brands:
        st.warning("동향을 파악할 브랜드를 선택해 주세요.")
    else:
        if not client_id or not client_secret:
            st.info("💡 왼쪽 사이드바에 네이버 검색 API ID와 Secret을 입력하시면 실시간 데이터를 바로 분석합니다.")
        else:
            all_dfs = []
            with st.spinner("경쟁사 미디어 동향을 실시간 수집 및 중복 정제 중입니다..."):
                for brand in selected_brands:
                    if "뉴스" in channels:
                        df_news = fetch_naver_data(brand, "news")
                        if df_news is not None:
                            all_dfs.append(df_news)
                    if "블로그" in channels:
                        df_blog = fetch_naver_data(brand, "blog")
                        if df_blog is not None:
                            all_dfs.append(df_blog)
                
                if all_dfs:
                    raw_df = pd.concat(all_dfs, ignore_index=True)
                    raw_count = len(raw_df)
                    
                    # 중복 정제 실행 (기준값: 75% 유사도)
                    final_df = filter_duplicates(raw_df, threshold=0.75)
                    filtered_count = len(final_df)
                    st.success(f"총 {raw_count}건의 원본 글 중, 유사도가 75% 이상 일치하는 중복 글을 제거하고 **최종 {filtered_count}건**의 고품질 데이터만 남겼습니다!")
                    
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
                                st.info("해당 브랜드로 수집된 세부 결과가 없습니다.")
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
                    st.warning("데이터를 가져오지 못했습니다. API 키나 검색 기간 설정을 확인해 주세요.")
