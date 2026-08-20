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
    if
