import streamlit as st
import pandas as pd
import altair as alt

# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="함창고 입시결과 대시보드", layout="wide")
st.title("함창고 입시결과 검색 · 시각화 툴 v2")
st.caption("※ 내부 참고용 · 상담 활용시 학생 개인정보는 가급적 숨기고 활용하시기 바랍니다.")


# ---------------- 1. 데이터 불러오기 + 전처리 ----------------
@st.cache_data
def load_data():
    # 1) CSV 불러오기
    try:
        df = pd.read_csv("admission_results.csv", encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv("admission_results.csv", encoding="euc-kr")

    # 2) 컬럼명 기본 정리
    # - 앞뒤 공백 제거
    # - 줄바꿈 제거
    df.columns = (
        df.columns.astype(str)
        .str.replace("\n", "", regex=False)
        .str.strip()
    )

    # 3) 컬럼명 표준화
    # CSV 파일마다 약간 다른 컬럼명을 하나의 이름으로 통일
    rename_map = {}

    for col in df.columns:
        compact = (
            str(col)
            .replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
            .strip()
        )

        if compact in ["졸업년도", "졸업연도"]:
            rename_map[col] = "졸업년도"

        elif compact in ["출신중", "출신중학교"]:
            rename_map[col] = "출신중"

        elif compact in ["성명", "이름", "학생명"]:
            rename_map[col] = "성명"

        elif compact in ["내신(중)", "중학교내신", "중학교내신성적", "중학교성적"]:
            rename_map[col] = "중학교내신"

        elif compact in ["내신(고)", "고교내신", "고등학교내신", "고등학교내신성적"]:
            rename_map[col] = "고교내신"

        elif compact in ["고입석차", "고입석차등급"]:
            rename_map[col] = "고입석차"

        elif compact in ["고등학교석차", "고등학교석차등급"]:
            rename_map[col] = "고등학교석차"

        elif compact in [
            "주요합격대학/전형/학과",
            "주요합격",
            "합격대학/전형/학과",
            "대학/전형/학과",
            "주요합격대학전형학과",
            "주요합격대학",
        ]:
            rename_map[col] = "주요합격"

        elif compact in ["최종단계", "최종결과", "합격결과"]:
            rename_map[col] = "최종단계"

        elif compact in ["전형명", "세부전형명"]:
            rename_map[col] = "전형명"

        elif compact in ["전형방법", "방법"]:
            rename_map[col] = "전형방법"

    df = df.rename(columns=rename_map)

    # 4) 필수 컬럼 안전장치
    required_cols = [
        "졸업년도",
        "출신중",
        "성명",
        "중학교내신",
        "고교내신",
        "고입석차",
        "고등학교석차",
        "주요합격",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    # 5) 숫자형 변환
    for col in ["졸업년도", "중학교내신", "고교내신", "고입석차", "고등학교석차"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.extract(r"(\d+\.?\d*)")[0]
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 졸업년도 없는 행 제거
    if "졸업년도" in df.columns:
        df = df[df["졸업년도"].notna()].copy()
        df["졸업년도"] = df["졸업년도"].astype(int)

    # 6) 주요합격 문자열에서 대학/전형/학과 정보 뽑기
    def parse_offer(text):
        res = {
            "대표대학": None,
            "전형유형원문": None,
            "대표학과": None,
        }

        if not isinstance(text, str) or not text.strip():
            return res

        first = text.split(",")[0].strip()
        parts = first.split("/")

        # 대학명
        uni_part = parts[0].strip()
        uni_name = uni_part.split("(")[0].strip()
        res["대표대학"] = uni_name

        # 전형유형
        if len(parts) > 1:
            res["전형유형원문"] = parts[1].strip()
        else:
            res["전형유형원문"] = uni_part

        # 학과
        if len(parts) > 2:
            res["대표학과"] = parts[2].strip()

        return res

    parsed = df["주요합격"].apply(parse_offer).apply(pd.Series)
    df = pd.concat([df, parsed], axis=1)

    # 7) 전형 대분류
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

    # 8) 학과 계열 분류
    def classify_major_group(major):
        if not isinstance(major, str):
            return "기타"

        text = major.replace(" ", "").strip()

        if any(k in text for k in ["의학", "의예", "치의", "약학", "한의", "수의", "간호"]):
            return "의학/보건계열"

        if any(k in text for k in [
            "기계", "전기", "전자", "화학", "컴퓨터", "소프트웨어",
            "공학", "건축", "토목", "환경", "AI", "인공지능", "정보"
        ]):
            return "공학/이공계열"

        if any(k in text for k in [
            "국어", "영어", "경영", "경제", "행정", "교육", "심리",
            "사회", "문헌", "복지", "법", "정치", "언론", "미디어"
        ]):
            return "인문/사회계열"

        if any(k in text for k in [
            "체육", "스포츠", "음악", "미술", "디자인", "무용",
            "연극", "영화", "영상", "패션"
        ]):
            return "예체능계열"

        return "기타"

    df["학과계열"] = df["대표학과"].apply(classify_major_group)

    # 9) 대학 그룹 플래그
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
        "서울과학기술대학교", "한국교통대학교", "군산대학교",
        "공주대학교", "안동대학교", "창원대학교", "부경대학교",
        "한국해양대학교", "목포대학교", "순천대학교"
    ]

    TEACHER_UNIS = [
        "서울교육대학교", "부산교육대학교", "대구교육대학교",
        "광주교육대학교", "경인교육대학교", "춘천교육대학교",
        "청주교육대학교", "공주교육대학교", "전주교육대학교",
        "진주교육대학교", "제주교육대학교"
    ]

    df["수도권대학"] = df["대표대학"].isin(CAPITAL_REGION_UNIS)
    df["국립대학"] = df["대표대학"].isin(NATIONAL_UNIS)

    def is_teacher_univ(name):
        if not isinstance(name, str):
            return False
        if ("교대" in name) or ("교육대" in name):
            return True
        return name in TEACHER_UNIS

    df["교대"] = df["대표대학"].apply(is_teacher_univ)

    # 10) 의치약한수, 간호 판별
    MED_KEYWORDS = [
        "의예", "의학", "의학부",
        "치의", "치의예", "치의학",
        "약학", "신약",
        "한의", "한의예", "한의학", "한의약",
        "수의", "수의예", "수의학"
    ]

    def is_med_major(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return any(keyword in text for keyword in MED_KEYWORDS)

    def is_nursing_major(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return "간호" in text

    df["의치약한수"] = df["대표학과"].apply(is_med_major)
    df["간호"] = df["대표학과"].apply(is_nursing_major)

    # 10-1) 의치약한수 세부 카테고리
    def is_med_school(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return (
            any(k in text for k in ["의예", "의학", "의학부"])
            and not any(k in text for k in ["치의", "한의", "수의"])
        )

    def is_dent_school(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return any(k in text for k in ["치의", "치의예", "치의학"])

    def is_pharm_school(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return any(k in text for k in ["약학", "신약"])

    def is_korean_med_school(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return any(k in text for k in ["한의", "한의예", "한의학", "한의약"])

    def is_vet_school(major):
        if not isinstance(major, str):
            return False
        text = major.replace(" ", "").strip()
        return any(k in text for k in ["수의", "수의예", "수의학"])

    df["의대"] = df["대표학과"].apply(is_med_school)
    df["치대"] = df["대표학과"].apply(is_dent_school)
    df["약대"] = df["대표학과"].apply(is_pharm_school)
    df["한의대"] = df["대표학과"].apply(is_korean_med_school)
    df["수의대"] = df["대표학과"].apply(is_vet_school)

    # 11) 농어촌 전형 플래그
    def is_rural_from_text(text):
        if not isinstance(text, str):
            return False
        return "농어촌" in text

    df["농어촌"] = df.apply(
        lambda row: (
            is_rural_from_text(row.get("전형유형원문", None)) or
            is_rural_from_text(row.get("주요합격", None))
        ),
        axis=1
    )

    # 12) 합격여부 처리
    # 최종단계가 있으면 우선 사용, 없으면 주요합격 문자열 기준
    positive_words = ["최초합격", "충원합격", "추가합격", "추합", "최종합격", "합격"]

    def decide_pass(row):
        final_stage = row.get("최종단계", None)
        offer = row.get("주요합격", None)

        if isinstance(final_stage, str) and final_stage.strip():
            text = final_stage.strip()
            if "불합격" in text:
                return "불합격"
            if any(word in text for word in positive_words):
                return "합격"

        if isinstance(offer, str) and offer.strip():
            return "합격"

        return "미상"

    df["합격여부"] = df.apply(decide_pass, axis=1)

    return df


# ---------------- 캐시 초기화 버튼 ----------------
if st.sidebar.button("🔄 최신 데이터 다시 불러오기"):
    st.cache_data.clear()
    st.rerun()


df = load_data()


# ---------------- 1-1. 데이터 진단 표시 ----------------
with st.expander("데이터 진단 정보 보기"):
    st.write("현재 앱이 읽은 전체 행 수:", len(df))

    if "졸업년도" in df.columns:
        st.write("졸업년도 목록:", sorted(df["졸업년도"].dropna().unique().tolist()))
        st.write("졸업년도별 인원:")
        st.dataframe(df["졸업년도"].value_counts().sort_index().reset_index().rename(
            columns={"index": "졸업년도", "졸업년도": "인원"}
        ))

    st.write("현재 인식된 컬럼 목록:")
    st.write(df.columns.tolist())


# ---------------- 2. 사이드바: 검색 조건 ----------------
st.sidebar.header("검색 조건")

# 졸업연도 범위
if "졸업년도" in df.columns and df["졸업년도"].notna().any():
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
    st.sidebar.warning("졸업년도 컬럼을 찾을 수 없습니다.")

# 출신 중학교
if "출신중" in df.columns:
    middle_options = ["전체"] + sorted(df["출신중"].dropna().astype(str).unique().tolist())
    selected_middle = st.sidebar.selectbox("출신 중학교", middle_options)
else:
    selected_middle = "전체"

# 대표대학 필터
if "대표대학" in df.columns:
    uni_counts = df["대표대학"].dropna().value_counts()
    major_universities = uni_counts.head(30).index.tolist()

    selected_universities = st.sidebar.multiselect(
        "대표 대학 (주요 4년제 위주)",
        options=major_universities,
        default=major_universities,
        help="우리 학교에서 합격자가 많은 상위 대학 위주의 목록입니다. 복수 선택 가능합니다.",
    )
else:
    selected_universities = []

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

# 전형 대분류
if "전형대분류" in df.columns:
    type_options = ["전체"] + sorted(df["전형대분류"].dropna().astype(str).unique().tolist())
    selected_type = st.sidebar.selectbox("전형 대분류", type_options)
else:
    selected_type = "전체"

# 학과 계열
if "학과계열" in df.columns:
    major_group_options = ["전체"] + sorted(df["학과계열"].dropna().astype(str).unique().tolist())
    selected_major_group = st.sidebar.selectbox("학과 계열", major_group_options)
else:
    selected_major_group = "전체"

# 의치약한수 세부 선택
med_view_option = st.sidebar.selectbox(
    "의치약한수 분류 필터",
    [
        "제한 없음",
        "의치약한수만(전체)",
        "의대만",
        "치대만",
        "약대만",
        "한의대만",
        "수의대만",
    ],
)

# 대학/전형/학과 키워드
keyword = st.sidebar.text_input(
    "대학/전형/학과 키워드",
    value="",
    placeholder="예: 서울대, 의학, 간호, 교대, 농어촌",
)

# 대학/전형 그룹 필터
st.sidebar.markdown("### 대학/전형 그룹 필터")
group_filter = st.sidebar.multiselect(
    "아래 그룹 중 포함하고 싶은 것 선택",
    options=["수도권대학", "국립대학", "의치약한수", "간호", "교대", "농어촌"],
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
if selected_middle != "전체" and "출신중" in filtered.columns:
    filtered = filtered[filtered["출신중"].astype(str) == selected_middle]

# 대표대학
if selected_universities and "대표대학" in filtered.columns:
    filtered = filtered[filtered["대표대학"].isin(selected_universities)]

# 고교 내신
if grade_range and "고교내신" in filtered.columns:
    filtered = filtered[
        (filtered["고교내신"] >= grade_range[0]) &
        (filtered["고교내신"] <= grade_range[1])
    ]

# 전형대분류
if selected_type != "전체" and "전형대분류" in filtered.columns:
    filtered = filtered[filtered["전형대분류"] == selected_type]

# 학과 계열
if selected_major_group != "전체" and "학과계열" in filtered.columns:
    filtered = filtered[filtered["학과계열"] == selected_major_group]

# 의치약한수 세부 필터
if med_view_option == "의치약한수만(전체)":
    filtered = filtered[filtered["의치약한수"] == True]
elif med_view_option == "의대만":
    filtered = filtered[filtered["의대"] == True]
elif med_view_option == "치대만":
    filtered = filtered[filtered["치대"] == True]
elif med_view_option == "약대만":
    filtered = filtered[filtered["약대"] == True]
elif med_view_option == "한의대만":
    filtered = filtered[filtered["한의대"] == True]
elif med_view_option == "수의대만":
    filtered = filtered[filtered["수의대"] == True]

# 키워드 검색
if keyword:
    keyword = keyword.strip()

    search_cols = [
        "주요합격",
        "대표대학",
        "전형유형원문",
        "대표학과",
        "전형명",
        "전형방법",
    ]

    available_search_cols = [col for col in search_cols if col in filtered.columns]

    if available_search_cols:
        mask = pd.Series(False, index=filtered.index)

        for col in available_search_cols:
            mask = mask | filtered[col].fillna("").astype(str).str.contains(keyword, case=False, na=False)

        filtered = filtered[mask]

# 대학/전형 그룹 필터
if group_filter:
    mask = pd.Series(False, index=filtered.index)

    for g in group_filter:
        if g in filtered.columns:
            mask = mask | (filtered[g] == True)

    filtered = filtered[mask]


# ---------------- 4. 메인 영역 ----------------
st.subheader("검색 결과 요약")
st.write(f"조건에 해당하는 학생 수: **{len(filtered)}명**")

# 화면에 보여줄 주요 컬럼
display_cols = [
    "졸업년도",
    "출신중",
    "성명",
    "중학교내신",
    "고입석차",
    "고교내신",
    "고등학교석차",
    "대표대학",
    "전형유형원문",
    "대표학과",
    "전형명",
    "전형방법",
    "주요합격",
    "합격여부",
]

display_cols = [col for col in display_cols if col in filtered.columns]

if display_cols:
    st.dataframe(filtered[display_cols], use_container_width=True)
else:
    st.dataframe(filtered, use_container_width=True)


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["대학별 합격자", "연도별 합격 추세", "중학교·전형·내신", "의대/간호/교대 분석", "데이터 구조 보기"]
)


# --- 탭 1: 대학별 합격자 인원 비교 ---
with tab1:
    st.markdown("### 대학별 합격자 인원 비교")

    df_uni = filtered[filtered["합격여부"] == "합격"].copy()

    if df_uni.empty:
        st.info("현재 필터 조건에서 합격 데이터가 없습니다.")
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
        st.dataframe(uni_count, use_container_width=True)


# --- 탭 2: 연도별 합격 추세 ---
with tab2:
    st.markdown("### 연도별 합격 추세")

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
        st.dataframe(trend, use_container_width=True)

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
                x=alt.X("졸업년도:O", title="졸업년도"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                color=alt.Color("전형대분류:N", title="전형"),
                tooltip=["졸업년도", "전형대분류", "합격자수"],
            )
            .properties(height=350)
        )

        st.altair_chart(chart_trend_type, use_container_width=True)
        st.dataframe(trend_type, use_container_width=True)


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
                    x=alt.X("출신중:N", title="출신중"),
                    y=alt.Y("평균내신:Q", title="평균 내신"),
                    color=alt.Color("전형대분류:N", title="전형"),
                    tooltip=["출신중", "전형대분류", "평균내신"],
                )
                .properties(height=350)
            )

            st.altair_chart(chart_pivot, use_container_width=True)
            st.dataframe(pivot, use_container_width=True)
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
        st.metric("의치약한수 합격자", len(med_df))

    with col2:
        st.metric("간호 계열 합격자", len(nur_df))

    with col3:
        st.metric("교대 합격자", len(tch_df))

    st.markdown("#### 의치약한수 합격자 수")
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
                x=alt.X("졸업년도:O", title="졸업년도"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                tooltip=["졸업년도", "합격자수"],
            )
            .properties(height=300)
        )

        st.altair_chart(chart_med, use_container_width=True)
        st.dataframe(med_df[display_cols], use_container_width=True)
    else:
        st.info("의치약한수 합격 데이터가 없습니다.")

    st.markdown("#### 간호 계열 합격자 수")
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
                x=alt.X("졸업년도:O", title="졸업년도"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                tooltip=["졸업년도", "합격자수"],
            )
            .properties(height=300)
        )

        st.altair_chart(chart_nur, use_container_width=True)
        st.dataframe(nur_df[display_cols], use_container_width=True)
    else:
        st.info("간호 계열 합격 데이터가 없습니다.")

    st.markdown("#### 교대 합격자 수")
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
                x=alt.X("졸업년도:O", title="졸업년도"),
                y=alt.Y("합격자수:Q", title="합격자 수"),
                tooltip=["졸업년도", "합격자수"],
            )
            .properties(height=300)
        )

        st.altair_chart(chart_tch, use_container_width=True)
        st.dataframe(tch_df[display_cols], use_container_width=True)
    else:
        st.info("교대 합격 데이터가 없습니다.")


# --- 탭 5: 데이터 구조 보기 ---
with tab5:
    st.markdown("### 데이터 컬럼 구조 확인")
    st.write("현재 데이터프레임의 컬럼 목록입니다.")
    st.write(df.columns.tolist())

    st.markdown("### 원본 데이터 앞부분")
    st.dataframe(df.head(20), use_container_width=True)

    if "졸업년도" in df.columns:
        st.markdown("### 졸업년도별 데이터 수")
        year_count = (
            df["졸업년도"]
            .value_counts()
            .sort_index()
            .reset_index()
        )
        year_count.columns = ["졸업년도", "인원"]
        st.dataframe(year_count, use_container_width=True)


# ---------------- 5. 화면 좌측 하단 만든이 표시 ----------------
st.markdown(
    """
    <div style="position: fixed; bottom: 10px; left: 10px; 
                font-size: 0.9rem; color: gray; background-color: rgba(255,255,255,0.7);
                padding: 4px 8px; border-radius: 4px;">
        만든이: 함창고 교사 박호종
    </div>
    """,
    unsafe_allow_html=True,
)
