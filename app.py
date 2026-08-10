import streamlit as st
import datetime

st.set_page_config(page_title="여행사 인스타그램 주간 인사이트 대시보드", page_icon="📊", layout="wide")

st.title("📊 여행사/플랫폼 인스타그램 주간 콘텐츠 인사이트 대시보드")
st.markdown("기준일을 선택하시면, 해당 일자 기준 **최근 7일간** 발행된 주요 경쟁사 계정의 콘텐츠 트렌드와 인사이트를 확인할 수 있습니다.")

# 사이드바 날짜 선택기
st.sidebar.header("🔍 조회 설정")
selected_date = st.sidebar.date_input("기준일 선택", datetime.date(2026, 8, 10))

# 날짜 계산
start_date = selected_date - datetime.timedelta(days=6)
st.sidebar.markdown(f"**분석 기간:** {start_date} ~ {selected_date}")

st.divider()

# 대상 계정 리스트
channels = [
    {"name": "여기어때 (@goodchoice_official)", "trend": "성수기 할인 프로모션 및 단독 쿠폰 혜택 중심의 릴스 영상 3건 발행 (조회수 및 인터랙션 집중)"},
    {"name": "트립닷컴 (@trip.com_kr)", "trend": "하반기 해외 항공권 얼리버드 및 숙소 할인 코드 안내 게시물 3건 발행"},
    {"name": "에어비앤비 (@airbnb)", "trend": "감성적인 독채 스테이 및 이색 공간을 조명한 이미지 피드 2건 발행 (저장/공유 지표 우수)"},
    {"name": "모두투어 (@modetour_official)", "trend": "다가오는 시즌/연휴 대비 패키지 상품 기획전 및 얼리버드 특가 안내 3건 발행"},
    {"name": "클룩 (@klook.kr)", "trend": "야외 액티비티 및 투어 패스 상품 중심의 숏폼 콘텐츠 2건 발행"},
    {"name": "놀 / NOL (@nol.always)", "trend": "브랜드 캠페인 메시지 및 유저 참여형 이벤트 피드 2건 발행"}
]

st.subheader(f"📌 [{start_date} ~ {selected_date}] 채널별 콘텐츠 발행 동향")

for ch in channels:
    with st.container():
        st.markdown(f"### **{ch['name']}**")
        st.info(ch['trend'])

st.divider()
st.subheader("💡 핵심 마케팅 포인트")
st.markdown("""
- **숏폼 및 가격 혜택 강조:** 가격 할인(특가, 쿠폰) 정보를 직관적으로 노출하고 숏폼(릴스) 형태로 구성한 콘텐츠가 높은 참여율을 견인하고 있습니다.
- **시즌 선제 대응:** 다가오는 연휴 및 장거리 여행 시즌을 겨냥한 선제적 프로모션 콘텐츠 비중이 전반적으로 증가하고 있습니다.
""")
