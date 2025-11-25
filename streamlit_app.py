import streamlit as st
import pandas as pd
import altair as alt

# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="함창고 입시결과 대시보드", layout="wide")
st.title("함창고 입시결과 검색 · 시각화 툴 v2")
st.caption("※ 내부 참고용 · 학생 개인정보는 가급적 익명(ID)으로 관리하세요.")


# ---------------- 1. 데이터 불러오기 + 전처리 ----------------
@st.cache_data
def load_data():
    # 1) CSV 불러오기 (utf-8-sig 먼저 시도, 안 되면 euc-kr)
    try:
        df = pd.read_csv("admission_results.csv", encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv("admission_results.csv", encoding="euc-kr")

    # 2) 열 이름 정리 (엑셀 열 이름과 다르면 오른쪽만 바꿔 주세요)
    df = df.rename(
        columns={
            "졸업년도": "졸업년도",
            "출신중": "출신중",
            "성명": "성명",
            "내신(중)": "중학교내신",
            "내신(고)": "고교내신",
            "고입석차": "고입석차",
            "고등학교석차": "고등학교석차",
            "고등학교\n석차": "고등학교석차",  # 개행 있는 경우 대비
            "주요 합격 대학/전형/학과": "주요합격",
        }
    )

    # 3) 숫자형 변환
    for col in ["졸업년도", "중학교내신", "고교내신", "고입석차", "고등학교석차"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4) '주요합격' 문자열에서 대학/전형/학과 정보 뽑기
    def parse_offer(text):
        res = {
            "대표대학": None,
            "전형유형원문": None,   # 예: 학생부교과(일반전형1), 정시(서울과학기술대)
            "대표학과": None,
        }
        if not isinstance(text, str) or not text.strip():
            return res

        first = text.split(",")[0].strip()   # 여러 개면 첫 번째만 사용
        parts = first.split("/")

        # 대학명
        uni_part = parts[0].strip()
        uni_name = uni_part.split("(")[0].strip()
        res["대표대학"] = uni_name

        # 전형유형
        if len(parts) > 1:
            res["전형유형원문"] = parts[1].strip()
        else:
            res["전형유형원문"] = uni_part  # '정시(서울과학기술대)' 같은 패턴

        # 학과
        if len(parts) > 2:
            res["대표학과"] = parts[2].strip()

        return res

    if "주요합격" in df.columns:
        parsed = df["주요합격"].apply(parse_offer).apply(pd.Series)
        df = pd.concat([df, parsed], axis=1)
    else:
        df["대표대학"] = None
        df["전형유형원문"] = None
        df["대표학과"] = None

    # 5) 전형 대분류(교과/종합/논술/정시/기타) 자동 분류
    def classify_type(text):
        if not isinstance(text, str):
            return "기타"
        if "교과" in text:
            return "교과"
        if "종합" in text:
            return "종합"
        if "논술" in text:
            return "논술"
        if "정시" in text:
            return "정시"
        return "기타"

    df["전형대분류"] = df["전형유형원문"].apply(classify_type)

    # 6) 학과 계열 분류 (아주 단순 규칙, 나중에 원하는 대로 키워드 추가 가능)
    def classify_major_group(major):
        if not isinstance(major, str):
            return "기타"
        if any(k in major for k in ["의학", "의예", "치의", "약학", "한의", "수의", "간호"]):
            return "의학/보건계열"
        if any(k in major for k in ["기계", "전기", "전자", "화학", "컴퓨터", "소프트웨어", "공학"]):
            return "공학/이공계열"
        if any(k in major for k in ["국어", "영어", "경영", "경제", "행정", "교육", "심리", "사회"]):
            return "인문/사회계열"
        if any(k in major for k in ["체육", "스포츠", "음악", "미술", "디자인", "무용"]):
            return "예체능계열"
        return "기타"

    df["학과계열"] = df["대표학과"].apply(classify_major_group)

    # 7) 대학 그룹(수도권/국립/교대/의치약한수/간호) 플래그
    CAPITAL_REGION_UNIS = [
        "서울대학교", "연세대학교", "고려대학교",
        "성균관대학교", "한양대학교", "서강대학교",
        "중앙대학교", "경희대학교", "한국외국어대학교",
        "서울시립대학교", "숭실대학교", "동국대학교",
        "건국대학교", "홍익대학교"
    ]

    NATIONAL_UNIS = [
        "서울대학교", "부산대학교", "경북대학교", "전남대학교",
        "전북대학교", "충남대학교", "충북대학교", "강원대학교",
        "제주대학교", "경상국립대학교", "금오공과대학교",
        "서울과학기술대학교", "한국교통대학교"
    ]

    TEACHER_UNIS = [
        "서울교육대학교", "부산교육대학교", "대구교육대학교",
        "광주교육대학교", "경인교육대학교", "춘천교육대학교",
        "청주교육대학교", "공주교육대학교", "전주교육대학교",
        "진주교육대학교", "제주교육대학교"
    ]

    MED_KEYWORDS = ["의학", "의예", "치의", "치과", "약학", "한의", "수의"]
    NURSING_KEYWORDS = ["간호"]

    df["수도권대학"] = df["대표대학"].isin(CAPITAL_REGION_UNIS)
    df["국립대학"] = df["대표대학"].isin(NATIONAL_UNIS)
    df["교대"] = df["대표대학"].isin(TEACHER_UNIS)

    def is_med_major(major):
        if not isinstance(major, str):
            return False
        return any(k in major for k in MED_KEYWORDS)

    def is_nursing_major(major):
        if not isinstance(major, str):
            return False
        return any(k in major for k in NURSING_KEYWORDS)

    df["의치약한수"] = df["대표학과"].apply(is_med_major)
    df["간호"] = df["대표학과"].apply(is_nursing_major)

    # 8) 합격여부 컬럼이 없으면, '주요합격'이 비어있지 않으면 합격으로 가정
    if "합격여부" not in df.columns:
        df["합격여부"] = df["주요합격"].apply(
            lambda x: "합격" if isinstance(x, str) and x.strip() else "미상"
        )

    return df


df = load_data()


# ---------------- 2. 사이드바: 검색 조건 ----------------
st.sidebar.header("검색 조건")

# 졸업연도 범위
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

# 출신 중학교
if "출신중" in df.columns:
    middle_options = ["전체"] + sorted(df["출신중"].dropna().unique().tolist())
    selected_middle = st.sidebar.selectbox("출신 중학교", middle_options)
else:
    selected_middle = "전체"

# 고교 내신
if "고교내신" in df.columns and df["고교내신"].notna().any():
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

# 전형 대분류 (교과/종합/논술/정시/기타)
type_options = ["전체"] + sorted(df["전형대분류"].dropna().unique().tolist())
selected_type = st.sidebar.selectbox("전형 대분류", type_options)

# 학과 계열
major_group_options = ["전체"] + sorted(df["학과계열"].dropna().unique().tolist())
selected_major_group = st.sidebar.selectbox("학과 계열", major_group_options)

# 대학/학과 키워드
keyword = st.sidebar.text_input(
    "대학/전형/학과 키워드 (예: 서울대, 의학, 간호, 교대 등)",
    value="",
)

# 대학 그룹 필터 (수도권, 국립, 의치약한수, 간호, 교대)
st.sidebar.markdown("### 대학 그룹 필터")
group_filter = st.sidebar.multiselect(
    "아래 그룹 중 포함하고 싶은 것 선택 (복수 선택 가능)",
    options=["수도권대학", "국립대학", "의치약한수", "간호", "교대"],
)

# ---------------- 3. 필터 적용 ----------------
filtered = df.copy()

# 졸업연도
if year_range and "졸업년도" in filtered.columns:
    filtered = filtered[
        (filtered["졸업년도"] >= year_range[0]) &
        (filtered["졸업년도"] <= year_range[1])
    ]

# 중학교
if selected_middle != "전체":
    filtered = filtered[filtered["출신중"] == selected_middle]

# 고교 내신
if grade_range and "고교내신" in filtered.columns:
    filtered = filtered[
        (filtered["고교내신"] >= grade_range[0]) &
        (filtered["고교내신"] <= grade_range[1])
    ]

# 전형대분류
if selected_type != "전체":
    filtered = filtered[filtered["전형대분류"] == selected_type]

# 학과 계열
if selected_major_group != "전체":
    filtered = filtered[filtered["학과계열"] == selected_major_group]

# 키워드 (주요합격 안에서 검색)
if keyword and "주요합격" in filtered.columns:
    filtered = filtered[filtered["주요합격"].fillna("").str.contains(keyword)]

# 대학 그룹 필터 (선택한 항목 중 하나라도 True이면 통과)
if group_filter:
    mask = pd.Series(False, index=filtered.index)
    for g in group_filter:
        if g in filtered.columns:
            mask = mask | (filtered[g] == True)
    filtered = filtered[mask]


# ---------------- 4. 메인 영역: 탭으로 나누기 ----------------
st.subheader("검색 결과 요약")
st.write(f"조건에 해당하는 학생 수: **{len(filtered)}명**")
st.dataframe(filtered)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["대학별 합격자", "연도별 합격 추세", "중학교·전형·내신", "의대/간호/교대 분석", "데이터 구조 보기"]
)

# --- 탭 1: 대학별 합격자 인원 비교 ---
with tab1:
    st.markdown("### 대학별 합격자 인원 비교")

    df_uni = filtered[filtered["합격여부"] == "합격"].copy()
    if df_uni.empty:
        st.info("현재 필터 조건에서 '합격' 데이터가 없습니다.")
    else:
        uni_count = (
            df_uni.groupby("대표대학")["성명"]
            .count()
            .reset_index(name="합격자수")
            .sort_values("합격자수", ascending=False)
        )
        chart_uni = (
            alt.Chart(uni_count)
            .mark_bar()
            .encode(
                x=alt.X("대표대학:N", sort="-y", title="대학"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                tooltip=["대표대학", "합격자수"],
            )
            .properties(height=350)
        )
        st.altair_chart(chart_uni, use_container_width=True)

# --- 탭 2: 연도별 합격 추세 ---
with tab2:
    st.markdown("### 연도별 합격 추세 (전체)")

    df_year = filtered[filtered["합격여부"] == "합격"].copy()
    if df_year.empty:
        st.info("합격 데이터가 없습니다.")
    else:
        trend = (
            df_year.groupby("졸업년도")["성명"]
            .count()
            .reset_index(name="합격자수")
            .sort_values("졸업년도")
        )
        chart_trend = (
            alt.Chart(trend)
            .mark_line(point=True)
            .encode(
                x=alt.X("졸업년도:O", title="졸업년도"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                tooltip=["졸업년도", "합격자수"],
            )
            .properties(height=350)
        )
        st.altair_chart(chart_trend, use_container_width=True)

        st.markdown("#### 전형 대분류별 연도별 추세")
        trend_type = (
            df_year.groupby(["졸업년도", "전형대분류"])["성명"]
            .count()
            .reset_index(name="합격자수")
        )
        chart_trend_type = (
            alt.Chart(trend_type)
            .mark_line(point=True)
            .encode(
                x="졸업년도:O",
                y="합격자수:Q",
                color="전형대분류:N",
                tooltip=["졸업년도", "전형대분류", "합격자수"],
            )
            .properties(height=350)
        )
        st.altair_chart(chart_trend_type, use_container_width=True)

# --- 탭 3: 중학교·전형·내신 분석 ---
with tab3:
    st.markdown("### 중학교별 · 전형대분류별 평균 내신 비교")

    if "출신중" in filtered.columns and not filtered.empty:
        df_valid = filtered.dropna(subset=["고교내신"])
        if df_valid.empty:
            st.info("내신 정보가 없습니다.")
        else:
            pivot = (
                df_valid.groupby(["출신중", "전형대분류"])["고교내신"]
                .mean()
                .reset_index(name="평균내신")
            )
            chart_pivot = (
                alt.Chart(pivot)
                .mark_bar()
                .encode(
                    x="출신중:N",
                    y="평균내신:Q",
                    color="전형대분류:N",
                    column="전형대분류:N",
                    tooltip=["출신중", "전형대분류", "평균내신"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart_pivot, use_container_width=True)
    else:
        st.info("출신중 정보가 없습니다.")

# --- 탭 4: 의대/간호/교대 분석 ---
with tab4:
    st.markdown("### 우리 학교 의대 · 간호 · 교대 진학 분석")

    med_df = filtered[(filtered["의치약한수"] == True) & (filtered["합격여부"] == "합격")]
    nur_df = filtered[(filtered["간호"] == True) & (filtered["합격여부"] == "합격")]
    tch_df = filtered[(filtered["교대"] == True) & (filtered["합격여부"] == "합격")]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 의치약한수 합격자 수 (연도별)")
        if not med_df.empty:
            med_trend = (
                med_df.groupby("졸업년도")["성명"]
                .count()
                .reset_index(name="합격자수")
            )
            chart_med = (
                alt.Chart(med_trend)
                .mark_line(point=True)
                .encode(
                    x="졸업년도:O",
                    y="합격자수:Q",
                    tooltip=["졸업년도", "합격자수"],
                )
                .properties(height=250)
            )
            st.altair_chart(chart_med, use_container_width=True)
        else:
            st.info("의치약한수 합격 데이터가 없습니다.")

    with col2:
        st.markdown("#### 간호 계열 합격자 수 (연도별)")
        if not nur_df.empty:
            nur_trend = (
                nur_df.groupby("졸업년도")["성명"]
                .count()
                .reset_index(name="합격자수")
            )
            chart_nur = (
                alt.Chart(nur_trend)
                .mark_line(point=True)
                .encode(
                    x="졸업년도:O",
                    y="합격자수:Q",
                    tooltip=["졸업년도", "합격자수"],
                )
                .properties(height=250)
            )
            st.altair_chart(chart_nur, use_container_width=True)
        else:
            st.info("간호 계열 합격 데이터가 없습니다.")

    with col3:
        st.markdown("#### 교대 합격자 수 (연도별)")
        if not tch_df.empty:
            tch_trend = (
                tch_df.groupby("졸업년도")["성명"]
                .count()
                .reset_index(name="합격자수")
            )
            chart_tch = (
                alt.Chart(tch_trend)
                .mark_line(point=True)
                .encode(
                    x="졸업년도:O",
                    y="합격자수:Q",
                    tooltip=["졸업년도", "합격자수"],
                )
                .properties(height=250)
            )
            st.altair_chart(chart_tch, use_container_width=True)
        else:
            st.info("교대 합격 데이터가 없습니다.")

# --- 탭 5: 데이터 구조 보기 ---
with tab5:
    st.markdown("### 데이터 컬럼 구조 확인")
    st.write("현재 데이터프레임의 컬럼 목록입니다.")
    st.write(df.columns.tolist())
    st.dataframe(df.head())


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
