import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json
import time

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="정신건강사회복지사 EMR 차팅 도우미",
    page_icon="📋",
    layout="wide"
)

# 2. 구조화된 출력(JSON) 스키마 정의
class ChartingOutput(BaseModel):
    high: list[str] = Field(description="수행도 '상' 환자용 서술형 EMR 차팅 문구 10개 (각 150~220자)")
    medium: list[str] = Field(description="수행도 '중' 환자용 서술형 EMR 차팅 문구 10개 (각 150~220자)")
    low: list[str] = Field(description="수행도 '하' 환자용 서술형 EMR 차팅 문구 10개 (각 150~220자)")

# 3. 임상 프롬프트 (System Instruction)
SYSTEM_INSTRUCTION = """
당신은 정신건강의학과 폐쇄병동 및 낮병동에서 근무하는 숙련된 정신건강사회복지사입니다.
입력된 집단 프로그램 영역과 세부 활동 주제를 바탕으로, 의무기록(EMR)에 바로 기재할 수 있는 객관적이고 전문적인 서술형 경과기록(Progress Note) 문구를 작성하세요.

[필수 작성 규칙]
1. 구성 및 분량: 수행도 상, 중, 하 등급별로 각각 10개씩(총 30개)의 서로 다른 문구를 작성하며, 각 문구는 공백 포함 150자~220자 내외로 작성할 것.
2. 문체: '~함.', '~임.', '~보임.', '~관찰됨.' 등 간결하고 객관적인 임상 의무기록(SOAP 중 O·A 중심) 종결어미를 사용할 것.
3. 개인정보 배제: 환자 이름, 성별, 나이, 병록번호 등 개인식별정보는 절대 포함하지 말고 '환자는', '프로그램 참여 시' 등으로 시작하거나 주어를 생략하여 서술할 것.
4. 다양성 확보: 10개의 예시가 복사-붙여넣기한 것처럼 보이지 않도록 관찰 행동(눈맞춤, 경청 태도, 발화 빈도, 감정 표현, 과제 수행력, 타 환자와의 상호작용 등)과 서술 구조를 매번 다르게 변주할 것.
5. 수행도별 임상 기준:
   - [상]: 프로그램 목적을 명확히 이해하고 자발적·적극적으로 참여함. 자신의 생각과 감정을 구체적으로 언어화하며, 집단원들과 지지적·건설적인 상호작용을 보임.
   - [중]: 진행자의 안내와 격려 하에 활동에 성실히 참여함. 기본적인 과제 수행은 원활하나, 자기 개방이나 집단 내 상호작용에서 다소 수동적이거나 부분적인 지지가 필요한 양상을 보임.
   - [하]: 주의집중력 저하, 무기력, 양성/음성 증상 또는 방어적 태도 등으로 인해 자발적 참여에 제한을 보임. 진행자의 반복적인 촉구와 개별적 개입 하에 최소한의 활동만 수행하거나 부분적으로 관찰만 유지함.
"""

# 4. API 키 확인 및 클라이언트 초기화
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 서버에 API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 5. AI 호출 함수 (503 일시적 혼잡 시 자동 재시도 기능 포함)
def generate_charts(category: str, topic: str):
    prompt = f"""
    [프로그램 영역]: {category}
    [세부 주제 및 활동 내용]: {topic}
    
    위 프로그램에 참여한 환자들을 위해 수행도 상, 중, 하 등급별로 각각 10개씩(총 30개)의 서로 다른 서술형 EMR 차팅 문구를 작성해 주세요.
    10개 문구 모두 어휘와 문장 시작 방식, 관찰 포인트를 다르게 구성하여 중복 느낌이 전혀 나지 않게 작성해 주세요.
    """
    
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ChartingOutput,
                    temperature=0.9,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                time.sleep(2)
                continue
            raise e

# 6. 웹앱 화면 UI 구성
st.title("📋 정신건강사회복지사 EMR 차팅 도우미")
st.caption("환자 개인정보를 입력하지 않고, 프로그램 주제와 수행도(상/중/하)에 따른 개별화 차팅 문구를 추천받습니다.")
st.divider()

col1, col2 = st.columns([1, 2])
with col1:
    category = st.selectbox(
        "프로그램 영역 선택",
        [
            "사회기술훈련",
            "정신건강교육(병식·약물·증상관리)",
            "인지재활 및 작업치료",
            "예술·음악·미술치료",
            "감정조절 및 스트레스 관리",
            "여가 및 신체활동",
            "퇴원계획 및 지역사회 적응훈련",
            "기타 집단프로그램"
        ]
    )

with col2:
    topic = st.text_input(
        "세부 주제 및 활동 내용",
        placeholder="예: 부당한 부탁 거절하기, 약물 부작용 대처법 나누기, 감정 카드 활용한 스트레스 표현"
    )

if st.button("✨ 차팅 문구 생성하기 (수행도별 10개씩)", type="primary", use_container_width=True):
    if not topic.strip():
        st.warning("세부 주제 및 활동 내용을 입력해 주세요.")
    else:
        with st.spinner("수행도별 10개씩 총 30개의 맞춤형 임상 차팅 문구를 생성하고 있습니다..."):
            try:
                st.session_state["chart_results"] = generate_charts(category, topic)
                st.session_state["last_category"] = category
                st.session_state["last_topic"] = topic
            except Exception as e:
                st.error(f"생성 중 오류가 발생했습니다: {e}")

# 7. 결과 출력 및 복사 기능 (우측 상단 복사 버튼 활용)
if "chart_results" in st.session_state:
    results = st.session_state["chart_results"]
    st.divider()
    
    # 새로고침(전체 재생성) 버튼
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.subheader(f"📝 추천 차팅 문구 ({st.session_state.get('last_category')} - {st.session_state.get('last_topic')})")
        st.caption("각 문구 우측 상단의 복사 아이콘(📋)을 누르면 클립보드에 바로 복사됩니다.")
    with header_col2:
        if st.button("🔄 새로운 30개 다시 생성", use_container_width=True):
            with st.spinner("새로운 표현으로 다시 생성 중..."):
                try:
                    st.session_state["chart_results"] = generate_charts(
                        st.session_state["last_category"],
                        st.session_state["last_topic"]
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 중 오류가 발생했습니다: {e}")

    tab_high, tab_mid, tab_low = st.tabs([
        "🟢 수행도 [상] (10개)",
        "🟡 수행도 [중] (10개)",
        "🔴 수행도 [하] (10개)"
    ])

    with tab_high:
        for idx, note in enumerate(results.get("high", []), 1):
            st.markdown(f"**옵션 {idx}** ({len(note)}자)")
            st.code(note, language=None)

    with tab_mid:
        for idx, note in enumerate(results.get("medium", []), 1):
            st.markdown(f"**옵션 {idx}** ({len(note)}자)")
            st.code(note, language=None)

    with tab_low:
        for idx, note in enumerate(results.get("low", []), 1):
            st.markdown(f"**옵션 {idx}** ({len(note)}자)")
            st.code(note, language=None)
