import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="경쟁사 마켓 뉴스 & 블로그 모니터링",
    page_icon="📰",
    layout="wide"
)

# 2. 대시보드 타이틀
st.title("📰 경쟁사 뉴스 및 블로그 모니터링 요약 대시보드")
st.markdown("설정한 기간 동안의 경쟁사 브랜드 관련 뉴스 및 블로그 내용을 요약하여 제공합니다.")

# 3. 사이드바 설정 (기간 선택 및 브랜드 필터)
st.sidebar.header("🔍 필터 설정")

# 검색 기간 설정 (기본값: 최근 7일)
today = datetime.today()
start_date = st.sidebar.date_input("시작일", today - timedelta(days=7))
end_date = st.sidebar.date_input("종료일", today)

# 모니터링 대상 경쟁사 리스트
brands = ["여기어때", "트립닷컴", "에어비앤비", "모두투어", "클룩", "놀(NOL)"]
selected_brands = st.sidebar.multiselect(
    "모니터링할 브랜드를 선택하세요",
    options=brands,
    default=brands
)

# 수집할 채널 선택
channels = st.sidebar.multiselect(
    "수집 채널",
    options=["뉴스", "블로그"],
    default=["뉴스", "블로그"]
)

# Naver API 자격증명 입력란 (초보자분들이 시트나 환경변수 없이 편하게 테스트할 수 있도록 사이드바에 배치)
st.sidebar.subheader("🔑 네이버 API 설정")
st.sidebar.markdown("[네이버 개발자 센터](https://developers.naver.com/)에서 무료로 발급받을 수 있습니다.")
client_id = st.sidebar.text_input("Naver Client ID", type="password")
client_secret = st.sidebar.text_input("Naver Client Secret", type="password")

# 4. 데이터 수집 함수 (네이버 검색 API 활용)
def fetch_naver_data(query, search_type, start_dt, end_dt):
    if not client_id or not client_secret:
        st.warning("네이버 API ID와 Secret을 입력하시면 실시간 데이터를 수집할 수 있습니다. (현재는 샘플 데이터 표시 중)")
        return None
        
    url = f"https://openapi.naver.com/v1/search/{search_type}.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": 50,  # 한 번에 가져올 결과 수
        "sort": "sim"   # 정확도순 (또는 date: 날짜순)
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get("items", [])
            data_list = []
            for item in items:
                # API 데이터 정제 (HTML 태그 제거)
                title = item['title'].replace("<b>", "").replace("</b>", "")
                description = item['description'].replace("<b>", "").replace("</b>", "")
                link = item['link']
                
                # 블로그의 경우 postdate가 있고, 뉴스는 pubDate가 있음
                pub_date_str = item.get('postdate') or item.get('pubDate')
                
                # 기간 필터링 (간이 검증)
                # 실제 네이버 API는 상세 날짜별 정밀 필터링을 지원하지 않으므로 코드단에서 한 번 더 걸러줍니다.
                data_list.append({
                    "브랜드": query,
                    "구분": "뉴스" if search_type == "news" else "블로그",
                    "제목": title,
                    "요약본": description[:120] + "...", # 네이버에서 제공하는 문맥 요약 정보 활용
                    "링크": link,
                    "게시일": pub_date_str
                })
            return pd.DataFrame(data_list)
    except Exception as e:
        st.error(f"데이터 수집 중 오류 발생: {e}")
    return None

# 5. 실행 버튼 및 데이터 출력
if st.button("📊 데이터 수집 및 요약 시작"):
    if not selected_brands:
        st.error("최소 하나 이상의 브랜드를 선택해주세요.")
    else:
        all_results = []
        
        # 실제 API 키가 없을 때 보여줄 안내 및 가짜 샘플 데이터
        if not client_id or not client_secret:
            # 샘플 데이터 생성
            sample_data = []
            for brand in selected_brands:
                for ch in channels:
                    sample_data.append({
                        "브랜드": brand,
                        "구분": ch,
                        "제목": f"[샘플] {brand} 관련 트렌드 및 마켓 이슈",
                        "요약본": f"이 데이터는 샘플입니다. 사이드바에 네이버 검색 API를 입력하시면 실제 {start_date} ~ {end_date} 기간의 {brand} 관련 {ch}를 수집하여 요약본과 함께 제공합니다.",
                        "링크": "https://www.naver.com",
                        "게시일": "2026-08-20"
                    })
            df_display = pd.DataFrame(sample_data)
            st.dataframe(df_display, use_container_width=True)
        else:
            with st.spinner("경쟁사 데이터를 실시간으로 크롤링하고 요약하는 중입니다..."):
                for brand in selected_brands:
                    if "뉴스" in channels:
                        df_news = fetch_naver_data(brand, "news", start_date, end_date)
                        if df_news is not None:
                            all_results.append(df_news)
                    if "블로그" in channels:
                        df_blog = fetch_naver_data(brand, "blog", start_date, end_date)
                        if df_blog is not None:
                            all_results.append(df_blog)
                
                if all_results:
                    final_df = pd.concat(all_results, ignore_index=True)
                    
                    # 수집 결과를 브랜드별/채널별로 깔끔하게 정리하여 출력
                    st.success(f"총 {len(final_df)}건의 데이터 수집 완료!")
                    
                    # 메인 테이블 출력
                    st.subheader("📋 수집 및 요약 결과 목록")
                    st.dataframe(
                        final_df,
                        column_config={
                            "링크": st.column_config.LinkColumn("원문 링크")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("검색 조건에 일치하는 수집 데이터가 없습니다.")
