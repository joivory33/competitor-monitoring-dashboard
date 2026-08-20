import streamlit as st
import pandas as pd
import requests
import datetime
import email.utils
import base64

# 1. 페이지 설정
st.set_page_config(
    page_title="경쟁사 마켓 트렌드 모니터링",
    page_icon="📰",
    layout="wide"
)

st.title("📰 경쟁사 뉴스 및 블로그 모니터링 요약")
st.markdown("설정한 기간 동안 **여기어때, 트립닷컴, 에어비앤비, 모두투어, 클룩, NOL** 관련 핵심 동향을 분석합니다.")

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
    # 이미 주소창에 저장된 유효한 키가 있다면 즉시 인증 처리
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
    
    # 🎯 [추가] 브라우저 저장 체크박스
    remember_me = st.checkbox("💾 내 브라우저에 이 API 키 기억하기 (이 대시보드를 북마크에 추가해 쓰세요!)", value=True)
        
    if st.button("🔑 인증키 등록 및 로그인"):
        if input_id and input_secret:
            st.session_state.naver_client_id = input_id
            st.session_state.naver_client_secret = input_secret
            st.session_state.api_authenticated = True
            
            # 주소창에 정보 인코딩하여 저장
            if remember_me:
                st.query_params["cid"] = encode_key(input_id)
                st.query_params["csec"] = encode_key(input_secret)
                
            st.rerun()  # 화면 새로고침하여 즉시 반영
        else:
            st.error("Client ID와 Client Secret을 모두 입력해 주세요.")

    # -----------------------------------------------------------------
    # 💡 [최종 상세 가이드] 미인증 상태일 때 메인 중앙에 시원하게 보여줄 상세 족집게 가이드
    # -----------------------------------------------------------------
    st.markdown("---")
    with st.expander("🔑 [초간단 1분] 네이버 API 발급 및 상세 설정 가이드 (여기서 보고 똑같이 체크하세요!)", expanded=True):
        st.markdown("""
        네이버의 정책 변경으로 인해 검색 API는 **네이버 클라우드 플랫폼(NCP)**에서 발급하셔야 합니다. 
        아래 설정을 똑같이 체크해주시면 승인 대기 없이 바로 완료됩니다!

        ### 1단계: 네이버 클라우드 콘솔 접속
        * **[네이버 클라우드 콘솔(NCP)](https://www.ncloud.com/)**에 접속하여 로그인합니다. (네이버 아이디로 간편 로그인 가능)

        ### 2단계: NAVER API HUB 메뉴 이동
        * 로그인 후 우측 상단의 **`[콘솔]`** 버튼을 클릭하여 대시보드로 이동합니다.
        * 왼쪽 메뉴에서 **`All Services` ➡️ `Application Services` ➡️ `NAVER API HUB`** 메뉴를 클릭합니다.
        * 화면 중앙의 **`+ Application 등록`** 버튼을 누릅니다.

        ### 3단계: 필수 및 선택 항목 세부 가이드 (★가장 중요)
        
        #### ① 사용 API 설정
        * **`사용 API`** 목록에서 **`네이버 로그인`**을 체크 선택합니다.
          * *NCP 정책 상, 검색 기능을 쓰기 위해서는 로그인 서비스를 필수 매핑해야 합니다.*

        #### ② 제공 정보 선택 (화면 상단 표)
        * **[회원이름, 연락처 이메일 주소, 별명, 프로필 사진, 성별, 생일, 연령대, 출생연도, 휴대전화번호]**
        * 🚨 **행동 지침**: 위 모든 항목의 **필수/추가 체크박스를 단 하나도 체크하지 않고 '전부 해제(빈칸)'**로 비워둡니다.
        * 💡 *이유: 대시보드는 검색 기능만 활용하며, 개인정보를 수집하지 않습니다. 하나라도 체크하면 보안 심사 대상으로 분류되어 API 사용이 즉시 차단되거나 보류됩니다.*

        #### ③ 로그인 오픈 API 서비스 환경 설정 (화면 하단 드롭다운)
        1. **`환경 추가`** 드롭다운 박스를 클릭하고 **`PC 웹`**을 선택해 추가합니다.
        2. 추가된 주소 입력창 두 곳에 아래의 대시보드 URL 주소를 동일하게 입력합니다.
           * **서비스 URL**: `https://instagram-insight-dashboard-yfksdz8sudm8rqyrxy3cqz.streamlit.app/`
           * **네이버 로그인 Callback URL**: `https://instagram-insight-dashboard-yfksdz8sudm8rqyrxy3cqz.streamlit.app/`

        #### ④ 이용 약관 동의 및 등록
        * 하단의 이용 약관 동의란에 체크한 뒤, 최종 **`등록하기`** 버튼을 누릅니다.

        ### 4단계: Client ID & Secret 입력
        * 등록이 완료되면 생성된 애플리케이션 우측의 **`[인증키 관리]`** 버튼을 클릭하여 발급된 **Client ID**와 **Client Secret**을 복사한 뒤, 대시보드 맨 위의 입력창에 붙여넣어 주세요!
        """)
else:
    # 인증 완료 상태 및 로그아웃 버튼
    col_status, col_btn = st.columns([5, 1])
    with col_status:
        st.success("✅ 네이버 API 인증 완료 - 대시보드가 정상 가동 중입니다.")
    with col_btn:
        if st.button("🔌 API 인증 정보 초기화"):
            st.session_state.naver_client_id = ""
            st.session_state.naver_client_secret = ""
            st.session_state.api_authenticated = False
            # 주소창에서도 정보 삭제
            st.query_params.clear()
            st.rerun()

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
    if not st.session_state.api_authenticated:
        st.warning("⚠️ 화면 상단에서 네이버 API 인증키를 먼저 등록해 주세요.")
    elif not selected_brands:
        st.warning("동향을 파악할 브랜드를 선택해 주세요.")
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
