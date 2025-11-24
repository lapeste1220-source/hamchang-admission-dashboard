import streamlit as st
import pandas as pd
import altair as alt

# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="함창고 입시결과 대시보드", layout="wide")
st.title("함창고 입시결과 검색 · 시각화 툴")

st.caption("※ 내부 참고용 · 학생 개인정보는 가급적 익명(ID)으로 관리하세요.")

# ---------------- 1. 데이터 불러오기 ----------------
@st.cache_data
def load_data():
    # admission_results.csv
    # 예: admission_results.csv  (같은 폴더에 있어야 합니다)
    df = pd.read_csv("admission_results.csv", encoding="utf-8-sig")

    # 열 이름을 조금 다루기 편하게 바꿔 둡니다.
    # (엑셀 열 이름과 다르면 여기 문자열을 실제 열 이름에 맞게 고쳐주세요)
    df = df.rename(
        columns={
            "졸업년도": "졸업년도",
            "출신중": "출신중",
            "성명": "성명",
            "내신(중)": "중학교내신",
            "내신(고)": "고교내신",
            "주요 합격 대학/전형/학과": "주요합격",
        }
    )

    # 숫자처럼 쓰고 싶은 열은 숫자로 변환
    for col in ["졸업년도", "중학교내신", "고교내신"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # '주요합격' 문자열에서 "대표 대학 이름"만 대충 뽑아내기
    # 예: "경운대학교(구미)/학생부교과(일반전형1)/의료서비스경영학과" -> "경운대학교"
    def extract_university(text):
        if not isinstance(text, str):
            return None
        first = text.split(",")[0]        # 여러 개 있으면 첫 번째만
        uni_part = first.split("/")[0]    # 맨 앞: 대학(지역)
        uni_name = uni_part.split("(")[0] # 괄호 앞까지만
        return uni_name.strip()

    if "주요합격" in df.columns:
        df["대표대학"] = df["주요합격"].apply(extract_university)
    else:
        df["대표대학"] = None

    return df

df = load_data()

# ---------------- 2. 사이드바에서 검색 조건 설정 ----------------
st.sidebar.header("검색 조건")

# (1) 졸업연도 범위 선택
if "졸업년도" in df.columns:
    min_year = int(df["졸업년도"].min())
    max_year = int(df["졸업년도"].max())
    year_range = st.sidebar.slider(
        "졸업연도 범위",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        step=1,
    )
else:
    year_range = None

# (2) 출신중학교 선택
if "출신중" in df.columns:
    middle_options = ["전체"] + sorted(df["출신중"].dropna().unique().tolist())
    selected_middle = st.sidebar.selectbox("출신 중학교", middle_options)
else:
    selected_middle = "전체"

# (3) 고교 내신 등급 범위
if "고교내신" in df.columns:
    min_grade = float(df["고교내신"].min())
    max_grade = float(df["고교내신"].max())
    grade_range = st.sidebar.slider(
        "고교 내신 등급 범위",
        min_value=round(min_grade, 1),
        max_value=round(max_grade, 1),
        value=(round(min_grade, 1), round(max_grade, 1)),
        step=0.1,
    )
else:
    grade_range = None

# (4) 대학/학과 키워드 (문자열 안에서 검색)
keyword = st.sidebar.text_input(
    "대학/전형/학과 키워드 (예: 서울대, 의학, 간호, 교대 등)",
    value="",
)

# ---------------- 3. 필터 적용 ----------------
filtered = df.copy()

# 졸업연도 필터
if year_range and "졸업년도" in filtered.columns:
    filtered = filtered[
        (filtered["졸업년도"] >= year_range[0]) &
        (filtered["졸업년도"] <= year_range[1])
    ]

# 출신중학교 필터
if "출신중" in filtered.columns and selected_middle != "전체":
    filtered = filtered[filtered["출신중"] == selected_middle]

# 고교 내신 필터
if grade_range and "고교내신" in filtered.columns:
    filtered = filtered[
        (filtered["고교내신"] >= grade_range[0]) &
        (filtered["고교내신"] <= grade_range[1])
    ]

# 키워드 필터 (주요합격 문자열 안에서 검색)
if keyword and "주요합격" in filtered.columns:
    filtered = filtered[filtered["주요합격"].fillna("").str.contains(keyword)]

# ---------------- 4. 결과 표 + 간단 그래프 ----------------
st.subheader("검색 결과")

st.write(f"조건에 해당하는 학생 수: **{len(filtered)}명**")
st.dataframe(filtered)

st.markdown("---")
st.subheader("대표 대학별 인원수 (간단 통계)")

if "대표대학" in filtered.columns and not filtered["대표대학"].dropna().empty:
    uni_count = (
        filtered.groupby("대표대학")["성명"]
        .count()
        .reset_index(name="인원수")
        .sort_values("인원수", ascending=False)
    )

    chart = (
        alt.Chart(uni_count)
        .mark_bar()
        .encode(
            x=alt.X("대표대학:N", sort="-y"),
            y="인원수:Q",
            tooltip=["대표대학", "인원수"],
        )
        .properties(height=300)
    )

    st.altair_chart(chart, use_container_width=True)
else:
    st.info("대표 대학 정보가 없거나, 필터 결과가 없습니다.")

# ---------------- 5. 화면 우측 하단 '만든이' 표시 ----------------
st.markdown(
    """
    <div style="position: fixed; bottom: 10px; right: 10px; 
                font-size: 0.9rem; color: gray; background-color: rgba(255,255,255,0.7);
                padding: 4px 8px; border-radius: 4px;">
        만든이: 함창고 교사 박호종
    </div>
    """,
    unsafe_allow_html=True,
)
