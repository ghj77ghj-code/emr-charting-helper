import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import json
import time #

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="정신건강사회복지사 EMR 차팅 도우미",
    page_icon="📋",
    layout="wide"
)

# 2. AI 응답 데이터 구조 정의 (수행도 상/중/하 각 3개씩 강제)
class ChartingOutput(BaseModel):
    high: list[str] = Field(description="수행도 '상' 수준 환자를 위한 서로 다른 서술형 EMR 차팅 문구 3개")
    medium: list[str] = Field(description="수행도 '중' 수준 환자를 위한 서로 다른 서술형 EMR 차팅 문구 3개")
    low: list[str] = Field(description="수행도 '하' 수준 환자를 위한 서로 다른 서술형 EMR 차팅 문구 3개")

# 3. 시스템 프롬프트 (정신건강사회복지학 임상 기록 매뉴얼)
SYSTEM_INSTRUCTION = """
너는 정신과 병원에서 근무하는 경력 10년 차 정신건강사회복지사(Mental Health Social Worker)다.
집단 프로그램 진행 후 다수의 환자에게 개별화된 의무기록(EMR)을 작성하는 업무를 돕기 위해, 주어진 [프로그램 영역]과 [세부 주제 및 활동 내용]에 맞춰 수행도(상/중/하)별 서술형 차팅 문구를 각 3개씩 생성하라.

[작성 원칙 및 임상 규격]
1. 문체 및 어미: 반드시 의무기록 형식의 간결한 평서문 어미('~함.', '~보임.', '~관찰됨.', '~필요함.')로 끝맺을 것.
2. 분량 및 구조: 환자 1명당 3~4문장(공백 포함 150~220자 내외)으로 작성하되, [프로그램 주제 및 목표 언급] -> [환자의 참여 태도 및 구체적 수행 반응] -> [정서 상태 및 치료적 평가/계획] 순서를 따를 것.
3. 개별화(차별화): 같은 등급 내 3개의 문구라도 어휘, 관찰된 행동 묘사, 정서적 반응 표현을 서로 다르게 변형하여 '복사-붙여넣기'로 보이지 않도록 작성할 것.
4. 객관적 서술: 추측성 표현('~인 것 같음')을 배제하고 관찰 가능한 언어적·비언어적 행동 중심으로 서술할 것.
5. 개인정보 배제: 특정 이름이나 병록번호 등은 절대 포함하지 말 것.

[수행도 등급별 임상 기준]
- 상(High): 프로그램 목표와 내용을 명확히 이해하고, 자발적·적극적으로 발언 및 과제에 참여함. 적절한 시선 접촉과 언어적·비언어적 표현을 보이며 타 환자에게도 지지적·긍정적 상호작용을 보임.
- 중(Medium): 기본적인 활동 규칙을 준수하며 참여하나, 다소 수동적이거나 집중력이 일시적으로 저하되는 모습이 관찰됨. 치료자의 언어적 촉구(Prompting) 및 격려 제공 시 과제를 무리 없이 수행함.
- 하(Low): 잔여 정신병적 증상(환청, 사고의 비약 등), 무기력, 졸음 또는 동기 부족으로 인해 과제 수행에 어려움이 큼. 활동 참여가 제한적이며 치료자의 지속적인 개별 개입과 정서적 지지가 요구됨.
"""

# 4. API 클라이언트 초기화 (Streamlit Secrets에서 안전하게 키 로드)
if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ 서버에 API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 5. AI 호출 함수 (503 일시적 혼잡 시 자동 재시도 기능 포함)
def generate_charts(category: str, topic: str, target_level: str = "ALL"):
    prompt = f"""
    [프로그램 영역]: {category}
    [세부 주제 및 활동 내용]: {topic}
    
    위 프로그램에 참여한 환자들을 위해 수행도 상, 중, 하 등급별로 각각 3개씩(총 9개)의 서로 다른 서술형 EMR 차팅 문구를 작성해 주세요.
    이전과 중복되지 않는 참신하고 자연스러운 임상 표현을 사용해 주세요.
    """
    
    # 일시적인 503 서버 혼잡 시 최대 3번까지 2초 간격으로 자동 재시도
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ChartingOutput,
                    temperature=0.85,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                time.sleep(2)
                continue
            raise e

# 6. 세션 상태 초기화 (화면 유지용)
if "chart_data" not in st.session_state:
    st.session_state.chart_data = None
if "copied_items" not in st.session_state:
    st.session_state.copied_items = set()

# 7. UI 화면 구성
st.title("📋 정신건강사회복지사 EMR 차팅 도우미")
st.caption("환자 개인정보를 입력하지 않고, 프로그램 주제와 수행도(상/중/하)에 따른 개별화 차팅 문구를 추천받습니다.")

st.divider()

# 입력 영역
col1, col2 = st.columns([1, 2])
with col1:
    preset_categories = ["직접 입력", "사회기술훈련", "약물증상교육", "인지재활프로그램", "예술·표현치료(미술/음악)", "사이코드라마", "일상생활훈련", "여가·집단활동"]
    selected_preset = st.selectbox("프로그램 영역 선택", preset_categories)
    if selected_preset == "직접 입력":
        category_input = st.text_input("프로그램 영역 직접 입력", placeholder="예: 스트레스 관리 훈련")
    else:
        category_input = selected_preset

with col2:
    topic_input = st.text_input(
        "세부 주제 및 활동 내용", 
        placeholder="예: 부당한 부탁 거절하기 (역할극을 통해 거절 의사 표현 연습)"
    )

generate_btn = st.button("✨ 차팅 문구 생성하기", type="primary", use_container_width=True)

# 전체 생성 버튼 클릭 시
if generate_btn:
    if not category_input.strip() or not topic_input.strip():
        st.warning("프로그램 영역과 세부 주제를 모두 입력해 주세요.")
    else:
        with st.spinner("임상 기록 매뉴얼에 맞춰 수행도별 차팅 문구를 생성하고 있습니다..."):
            try:
                st.session_state.chart_data = generate_charts(category_input, topic_input)
                st.session_state.copied_items = set() # 새로 생성 시 복사 표시 초기화
            except Exception as e:
                st.error(f"생성 중 오류가 발생했습니다: {e}")

# 결과 출력 영역 (수행도 상 / 중 / 하 3단 배치)
if st.session_state.chart_data:
    st.divider()
    st.info("💡 각 문구 우측 상단의 **복사 아이콘(📄)**을 클릭하면 클립보드에 즉시 복사됩니다. 문구를 모두 사용하셨다면 각 등급 상단의 **[🔄 새로고침]** 버튼을 눌러 새로운 문구를 받아보세요.")
    
    levels = [
        ("high", "🟢 수행도: 상 (적극적 참여·우수)", "high_refresh"),
        ("medium", "🟡 수행도: 중 (부분적 참여·촉구 필요)", "med_refresh"),
        ("low", "🔴 수행도: 하 (참여 제한·지속 개입 필요)", "low_refresh")
    ]
    
    cols = st.columns(3)
    
    for idx, (key, title, btn_key) in enumerate(levels):
        with cols[idx]:
            # 등급 헤더 및 개별 새로고침 버튼
            header_col, btn_col = st.columns([3, 1.3])
            with header_col:
                st.subheader(title)
            with btn_col:
                if st.button("🔄 새로고침", key=btn_key, help=f"{title} 문구 3개만 새로 받아옵니다"):
                    with st.spinner("새 문구 생성 중..."):
                        try:
                            new_data = generate_charts(category_input, topic_input)
                            st.session_state.chart_data[key] = new_data[key]
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류: {e}")
            
            # 문구 3개 카드 출력
            for i, text in enumerate(st.session_state.chart_data[key]):
                with st.container(border=True):
                    st.markdown(f"**추천 {i+1}**")
                    # st.code는 우측 상단에 원클릭 복사 버튼을 기본 제공하며 자동 줄바꿈 지원
                    st.code(text, language=None, wrap_lines=True)