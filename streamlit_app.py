import re
import streamlit as st
import pandas as pd
import altair as alt


# ---------------- 기본 설정 ----------------
st.set_page_config(page_title="함창고 입시결과 대시보드", layout="wide")

st.title("함창고 입시결과 검색 · 시각화 툴 v2")
st.caption("※ 내부 참고용 · 상담 활용시 학생 개인정보는 가급적 숨기고 활용하시기 바랍니다.")


# ---------------- 유틸 함수 ----------------
def normalize_col_name(col):
    """컬럼명 비교용 정규화"""
    text = str(col)
    text = text.replace("\ufeff", "")
    text = text.replace("\xa0", "")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def first_existing_column(df, candidates):
    """후보 컬럼명 중 실제 df에 존재하는 첫 번째 컬럼명 반환"""
    normalized_map = {normalize_col_name(c): c for c in df.columns}

    for cand in candidates:
        key = normalize_col_name(cand)
        if key in normalized_map:
            return normalized_map[key]

    return None


def safe_to_numeric(series):
    """문자열 안 숫자만 추출해서 숫자형 변환"""
    return pd.to_numeric(
        series.astype(str).str.extract(r"(\d+\.?\d*)")[0],
        errors="coerce"
    )


def has_visible_values(df, col):
    """화면 표시할 가치가 있는 값이 있는 컬럼인지 확인"""
    if col not in df.columns:
        return False

    s = df[col].fillna("").astype(str).str.strip()
    s = s[~s.str.lower().isin(["", "none", "nan"])]
    return len(s) > 0


def read_admission_file(file_path):
    """
    admission_results.csv를 안전하게 읽는 함수.

    처리 내용:
    1. 파일 앞부분에 제목행/빈행이 있어도 실제 헤더 행 자동 탐색
    2. 탭 구분, 쉼표 구분, 세미콜론 구분, 파이프 구분 자동 감지
    3. utf-8-sig, utf-8, cp949, euc-kr 인코딩 대응
    4. 데이터 줄의 칸 수가 헤더보다 많으면 마지막 컬럼에 합쳐서 보존
    """

    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    text = None
    used_encoding = None
    last_error = None

    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="replace") as f:
                text = f.read()
            used_encoding = enc
            break
        except Exception as e:
            last_error = e

    if text is None:
        raise ValueError(f"{file_path} 파일을 열 수 없습니다. 마지막 오류: {last_error}")

    lines = text.splitlines()
    lines = [line for line in lines if line.strip()]

    if not lines:
        raise ValueError(f"{file_path} 파일이 비어 있습니다.")

    # 실제 헤더 행 찾기
    # 예: 1행에 '출신중학교별 대입전형 결과...' 같은 제목이 있을 수 있음
    header_idx = None

    for i, line in enumerate(lines):
        compact = (
            line.replace(" ", "")
            .replace("\t", "")
            .replace(",", "")
            .replace(";", "")
            .replace("|", "")
        )

        if ("졸업년도" in compact or "졸업연도" in compact) and "성명" in compact:
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(
            "실제 헤더 행을 찾지 못했습니다. "
            "파일 안에 '졸업년도'와 '성명'이 들어간 제목 행이 있는지 확인해 주세요."
        )

    header_line = lines[header_idx]
    data_lines = lines[header_idx + 1:]

    # 헤더 줄 기준으로 구분자 판단
    delimiter_candidates = ["\t", ",", ";", "|"]
    delimiter = max(delimiter_candidates, key=lambda d: header_line.count(d))

    if header_line.count(delimiter) == 0:
        raise ValueError(
            "헤더 행에서 구분자를 찾지 못했습니다. "
            "엑셀에서 CSV UTF-8 또는 탭 구분 텍스트로 다시 저장해 주세요."
        )

    # 헤더 처리
    headers = [h.strip().strip('"').strip("'") for h in header_line.split(delimiter)]
    headers = [
        h.replace("\ufeff", "").replace("\n", "").replace("\r", "").strip()
        for h in headers
    ]

    headers = [
        h if h else f"빈컬럼{i + 1}"
        for i, h in enumerate(headers)
    ]

    col_count = len(headers)

    if col_count <= 1:
        raise ValueError(
            "컬럼이 1개로만 인식되었습니다. "
            "CSV의 실제 헤더가 탭/쉼표 등으로 구분되어 있는지 확인해 주세요."
        )

    # 데이터 줄 처리
    rows = []

    for line in data_lines:
        if not line.strip():
            continue

        parts = line.split(delimiter)

        if len(parts) < col_count:
            parts = parts + [""] * (col_count - len(parts))

        elif len(parts) > col_count:
            # 뒤쪽 주요합격 내용에 구분자가 들어간 경우 마지막 컬럼으로 합침
            parts = parts[:col_count - 1] + [delimiter.join(parts[col_count - 1:])]

        cleaned = []

        for p in parts:
            cell = str(p).strip()

            if len(cell) >= 2 and cell[0] == '"' and cell[-1] == '"':
                cell = cell[1:-1]

            cell = cell.replace('""', '"')
            cleaned.append(cell)

        rows.append(cleaned)

    df = pd.DataFrame(rows, columns=headers)

    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.replace("\n", "", regex=False)
        .str.replace("\r", "", regex=False)
        .str.strip()
    )

    df.attrs["read_info"] = (
        f"{used_encoding} / 직접 줄 단위 읽기 / "
        f"헤더 행: {header_idx + 1}행 / 구분자: {repr(delimiter)}"
    )

    return df


def find_offer_column(df):
    """
    주요 합격 대학/전형/학과 컬럼을 찾습니다.
    컬럼명이 다소 달라도, 내용에 대학/전형/학과 정보가 많은 컬럼을 자동 탐색합니다.
    """

    candidates = [
        "주요 합격 대학/전형/학과",
        "주요합격대학/전형/학과",
        "주요합격",
        "합격대학/전형/학과",
        "대학/전형/학과",
        "주요 합격",
        "주요합격대학전형학과",
        "주요합격대학",
    ]

    found = first_existing_column(df, candidates)
    if found:
        return found

    # 컬럼명 기반 2차 탐색
    for c in df.columns:
        compact = normalize_col_name(c)
        if "합격" in compact and ("대학" in compact or "전형" in compact or "학과" in compact):
            return c

    # 내용 기반 3차 탐색
    known_cols = {
        "졸업년도", "졸업연도", "출신중", "출신중학교", "성명", "이름", "학생명",
        "내신(중)", "중학교내신", "중학교내신성적",
        "내신(고)", "고교내신", "고등학교내신",
        "고입석차", "고등학교석차", "고등학교 석차",
    }
    known_normalized = {normalize_col_name(x) for x in known_cols}

    best_col = None
    best_score = -1

    for c in df.columns:
        if normalize_col_name(c) in known_normalized:
            continue

        s = df[c].fillna("").astype(str)

        score = 0
        score += s.str.contains("대학교|대학|교대|교육대", regex=True).sum() * 3
        score += s.str.contains("학생부|교과|종합|정시|논술|전형", regex=True).sum() * 2
        score += s.str.contains("학과|학부|전공|계열", regex=True).sum() * 2
        score += s.str.contains("/", regex=False).sum()
        score += s.str.contains(" - ", regex=False).sum()

        if score > best_score:
            best_score = score
            best_col = c

    if best_score > 0:
        return best_col

    return None


def repair_offer_and_high_rank(df):
    """
    주요합격 앞에 붙은 고등학교석차 숫자를 복구합니다.

    예:
    10;"대구대학교(경산)/학생부교과/체육학과"
    → 고등학교석차 = 10
    → 주요합격 = 대구대학교(경산)/학생부교과/체육학과
    """

    if "주요합격" not in df.columns:
        return df

    if "고등학교석차" not in df.columns:
        df["고등학교석차"] = None

    offer_text = df["주요합격"].fillna("").astype(str)

    # 숫자 + ; 또는 숫자 + , 다음에 대학 정보가 붙는 경우
    extracted = offer_text.str.extract(r'^\s*"?(\d+)\s*[;,]\s*"?(.+)$')

    mask = extracted[0].notna() & extracted[1].notna()

    high_rank_empty = (
        df["고등학교석차"].isna()
        | (df["고등학교석차"].astype(str).str.strip() == "")
        | (df["고등학교석차"].astype(str).str.strip().str.lower() == "none")
        | (df["고등학교석차"].astype(str).str.strip().str.lower() == "nan")
    )

    df.loc[mask & high_rank_empty, "고등학교석차"] = extracted.loc[mask & high_rank_empty, 0]

    # 주요합격에서는 앞 숫자 제거
    df.loc[mask, "주요합격"] = extracted.loc[mask, 1]

    # 남아 있는 따옴표 정리
    df["주요합격"] = (
        df["주요합격"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.strip('"')
        .str.strip("'")
        .str.replace('""', '"', regex=False)
    )

    return df


# ---------------- 1. 데이터 불러오기 + 전처리 ----------------
@st.cache_data
def load_data():
    df = read_admission_file("admission_results.csv")

    df.columns = (
        df.columns.astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.replace("\n", "", regex=False)
        .str.replace("\r", "", regex=False)
        .str.strip()
    )

    # 주요 컬럼 자동 인식
    col_graduation = first_existing_column(df, ["졸업년도", "졸업연도"])
    col_middle = first_existing_column(df, ["출신중", "출신중학교"])
    col_name = first_existing_column(df, ["성명", "이름", "학생명"])

    col_middle_grade = first_existing_column(
        df,
        ["내신(중)", "중학교내신", "중학교 내신", "중학교내신성적", "중학교 내신성적"]
    )

    col_high_grade = first_existing_column(
        df,
        ["내신(고)", "고교내신", "고교 내신", "고등학교내신", "고등학교 내신"]
    )

    col_middle_rank = first_existing_column(df, ["고입석차", "고입 석차"])
    col_high_rank = first_existing_column(
        df,
        ["고등학교석차", "고등학교 석차", "고등학교\n석차", "고등학교서차"]
    )

    col_offer = find_offer_column(df)

    col_final_stage = first_existing_column(df, ["최종단계", "최종 단계", "최종결과", "합격결과"])
    col_admission_name = first_existing_column(df, ["전형명", "세부전형명", "전형 이름"])
    col_admission_method = first_existing_column(df, ["전형방법", "전형 방법", "방법"])

    # 표준 컬럼 생성
    df["졸업년도"] = df[col_graduation] if col_graduation else None
    df["출신중"] = df[col_middle] if col_middle else None
    df["성명"] = df[col_name] if col_name else None
    df["중학교내신"] = df[col_middle_grade] if col_middle_grade else None
    df["고교내신"] = df[col_high_grade] if col_high_grade else None
    df["고입석차"] = df[col_middle_rank] if col_middle_rank else None
    df["고등학교석차"] = df[col_high_rank] if col_high_rank else None
    df["주요합격"] = df[col_offer] if col_offer else ""

    df["최종단계"] = df[col_final_stage] if col_final_stage else ""
    df["전형명"] = df[col_admission_name] if col_admission_name else ""
    df["전형방법"] = df[col_admission_method] if col_admission_method else ""

    # 주요합격 앞에 붙은 고등학교석차 숫자 복구
    df = repair_offer_and_high_rank(df)

    # 숫자형 변환
    for col in ["졸업년도", "중학교내신", "고교내신", "고입석차", "고등학교석차"]:
        df[col] = safe_to_numeric(df[col])

    # 졸업년도 정상 범위만 사용
    df = df[df["졸업년도"].notna()].copy()
    df = df[(df["졸업년도"] >= 2000) & (df["졸업년도"] <= 2100)].copy()

    if df.empty:
        raise ValueError(
            "졸업년도 데이터를 찾지 못했습니다. "
            "CSV 파일의 졸업년도/졸업연도 컬럼명을 확인해 주세요."
        )

    df["졸업년도"] = df["졸업년도"].astype(int)

    # 주요합격 문자열에서 대표대학/전형/학과 추출
    def parse_offer(text):
        result = {
            "대표대학": "",
            "전형유형원문": "",
            "대표학과": "",
        }

        if not isinstance(text, str):
            return result

        text = text.strip().strip('"').strip("'")
        if not text:
            return result

        # 여러 합격 결과 중 첫 번째를 대표값으로 사용
        first = text.split(",")[0].strip()

        # 혹시 또 숫자; 이 남아 있으면 제거
        first = re.sub(r'^\s*\d+\s*[;,]\s*"?', "", first).strip().strip('"').strip("'")

        # 기존 자료: 대학/전형/학과
        if "/" in first:
            parts = [p.strip() for p in first.split("/")]

        # 2026 자료: 대학 - 전형 - 학과
        elif " - " in first:
            parts = [p.strip() for p in first.split(" - ")]

        # 하이픈 주변 공백이 불규칙한 경우
        elif "-" in first:
            parts = [p.strip() for p in first.split("-")]

        else:
            parts = [first]

        if len(parts) >= 1:
            uni_part = parts[0]
            result["대표대학"] = uni_part.split("(")[0].strip()

        if len(parts) >= 2:
            result["전형유형원문"] = parts[1].strip()
        else:
            result["전형유형원문"] = first

        if len(parts) >= 3:
            result["대표학과"] = parts[2].strip()

        return result

    parsed = df["주요합격"].fillna("").astype(str).apply(parse_offer).apply(pd.Series)

    for col in ["대표대학", "전형유형원문", "대표학과"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    df = pd.concat([df, parsed[["대표대학", "전형유형원문", "대표학과"]]], axis=1)

    for col in ["대표대학", "전형유형원문", "대표학과"]:
        if col not in df.columns:
            df[col] = ""

    df["대표대학"] = df["대표대학"].fillna("").astype(str)
    df["전형유형원문"] = df["전형유형원문"].fillna("").astype(str)
    df["대표학과"] = df["대표학과"].fillna("").astype(str)

    # 전형 대분류
    def classify_type(text):
        if not isinstance(text, str):
            return "기타"

        text = text.strip()

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

    # 학과 계열 분류
    def classify_major_group(major):
        if not isinstance(major, str):
            return "기타"

        text = major.replace(" ", "").strip()

        if any(k in text for k in ["의학", "의예", "치의", "약학", "한의", "수의", "간호"]):
            return "의학/보건계열"

        if any(k in text for k in [
            "기계", "전기", "전자", "화학", "컴퓨터", "소프트웨어",
            "공학", "건축", "토목", "환경", "AI", "인공지능", "정보",
            "데이터", "반도체", "로봇", "자동차", "에너지"
        ]):
            return "공학/이공계열"

        if any(k in text for k in [
            "국어", "영어", "경영", "경제", "행정", "교육", "심리",
            "사회", "문헌", "복지", "법", "정치", "언론", "미디어",
            "역사", "철학", "문화", "관광", "유아교육", "초등교육"
        ]):
            return "인문/사회계열"

        if any(k in text for k in [
            "체육", "스포츠", "음악", "미술", "디자인", "무용",
            "연극", "영화", "영상", "패션", "뷰티"
        ]):
            return "예체능계열"

        return "기타"

    df["학과계열"] = df["대표학과"].apply(classify_major_group)

    # 대학 그룹
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
        "한국해양대학교", "목포대학교", "순천대학교",
        "한국교원대학교", "한국체육대학교"
    ]

    TEACHER_UNIS = [
        "서울교육대학교", "부산교육대학교", "대구교육대학교",
        "광주교육대학교", "경인교육대학교", "춘천교육대학교",
        "청주교육대학교", "공주교육대학교", "전주교육대학교",
        "진주교육대학교", "제주교육대학교"
    ]

def normalize_university_name(name):
    """
    대학명 표준화 함수.
    예:
    서울대 → 서울대학교
    경북대 → 경북대학교
    대구대 → 대구대학교
    영남대 → 영남대학교
    한국외대 → 한국외국어대학교
    대구교대 → 대구교육대학교
    """

    if not isinstance(name, str):
        return ""

    text = (
        name.replace(" ", "")
        .replace("　", "")
        .replace("(서울)", "")
        .replace("(경산)", "")
        .replace("(대구)", "")
        .replace("(경북)", "")
        .replace("(부산)", "")
        .replace("(천안)", "")
        .replace("(글로벌)", "")
        .strip()
    )

    # 특수 약칭 처리
    alias_map = {
        "서울대": "서울대학교",
        "연세대": "연세대학교",
        "고려대": "고려대학교",
        "서강대": "서강대학교",
        "성균관대": "성균관대학교",
        "한양대": "한양대학교",
        "중앙대": "중앙대학교",
        "경희대": "경희대학교",
        "한국외대": "한국외국어대학교",
        "외대": "한국외국어대학교",
        "서울시립대": "서울시립대학교",
        "시립대": "서울시립대학교",
        "건국대": "건국대학교",
        "동국대": "동국대학교",
        "홍익대": "홍익대학교",
        "숭실대": "숭실대학교",

        "경북대": "경북대학교",
        "부산대": "부산대학교",
        "전남대": "전남대학교",
        "전북대": "전북대학교",
        "충남대": "충남대학교",
        "충북대": "충북대학교",
        "강원대": "강원대학교",
        "제주대": "제주대학교",
        "경상국립대": "경상국립대학교",
        "금오공대": "금오공과대학교",
        "금오공과대": "금오공과대학교",
        "서울과기대": "서울과학기술대학교",
        "서울과학기술대": "서울과학기술대학교",
        "교통대": "한국교통대학교",
        "한국교통대": "한국교통대학교",
        "군산대": "군산대학교",
        "공주대": "공주대학교",
        "안동대": "안동대학교",
        "창원대": "창원대학교",
        "부경대": "부경대학교",
        "한국해양대": "한국해양대학교",
        "목포대": "목포대학교",
        "순천대": "순천대학교",
        "한국교원대": "한국교원대학교",
        "한국체대": "한국체육대학교",
        "한국체육대": "한국체육대학교",

        "영남대": "영남대학교",
        "계명대": "계명대학교",
        "대구대": "대구대학교",
        "대구가톨릭대": "대구가톨릭대학교",
        "대가대": "대구가톨릭대학교",
        "대구한의대": "대구한의대학교",
        "동국대WISE": "동국대학교WISE캠퍼스",
        "동국대와이즈": "동국대학교WISE캠퍼스",
        "동국대학교WISE": "동국대학교WISE캠퍼스",
        "동양대": "동양대학교",
        "경운대": "경운대학교",
        "위덕대": "위덕대학교",
        "김천대": "김천대학교",
        "대구교대": "대구교육대학교",
        "부산교대": "부산교육대학교",
        "서울교대": "서울교육대학교",
        "경인교대": "경인교육대학교",
        "청주교대": "청주교육대학교",
        "공주교대": "공주교육대학교",
        "전주교대": "전주교육대학교",
        "진주교대": "진주교육대학교",
        "춘천교대": "춘천교육대학교",
        "광주교대": "광주교육대학교",
        "제주교대": "제주교육대학교",
    }

    if text in alias_map:
        return alias_map[text]

    # 이미 '대학교'로 끝나면 그대로 사용
    if text.endswith("대학교"):
        return text

    # '교육대' → '교육대학교'
    if text.endswith("교육대"):
        return text[:-1] + "학교"

    # '교대'는 교육대학교로 바꾸기 어렵지만, 자주 쓰는 약칭은 위 alias_map에서 처리
    if text.endswith("교대"):
        return text

    # 일반적인 '~대' → '~대학교'
    # 예: 영남대 → 영남대학교, 대구대 → 대구대학교
    if text.endswith("대") and len(text) >= 3:
        return text[:-1] + "대학교"

    return text

    # 이미 '서울대학교'처럼 되어 있으면 그대로 사용
    if text.endswith("대학교"):
        return text

    # '경희대'처럼 alias_map에 없는 '○○대'는 일단 그대로 둠
    return text

    df["대표대학정규화"] = df["대표대학"].apply(normalize_university_name)

    # 화면 표시와 집계도 표준 대학명으로 통일
    df["대표대학"] = df["대표대학정규화"]

    capital_set = set([normalize_university_name(x) for x in CAPITAL_REGION_UNIS])
    national_set = set([normalize_university_name(x) for x in NATIONAL_UNIS])
    teacher_set = set([normalize_university_name(x) for x in TEACHER_UNIS])

    df["수도권대학"] = df["대표대학정규화"].isin(capital_set)
    df["국립대학"] = df["대표대학정규화"].isin(national_set)

    def is_teacher_univ(name):
        if not isinstance(name, str):
            return False

        text = name.replace(" ", "").strip()

        if ("교대" in text) or ("교육대" in text):
            return True

        return normalize_university_name(text) in teacher_set

    df["교대"] = df["대표대학"].apply(is_teacher_univ)

    # 의치약한수, 간호
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

    # 농어촌
    def contains_rural(text):
        if not isinstance(text, str):
            return False
        return "농어촌" in text

    df["농어촌"] = df.apply(
        lambda row: (
            contains_rural(row.get("전형유형원문", "")) or
            contains_rural(row.get("주요합격", "")) or
            contains_rural(row.get("전형명", "")) or
            contains_rural(row.get("전형방법", ""))
        ),
        axis=1
    )

    # 합격여부 처리
    positive_words = ["최초합격", "충원합격", "추가합격", "추합", "최종합격", "합격"]

    def decide_pass(row):
        final_stage = row.get("최종단계", "")
        offer = row.get("주요합격", "")

        if isinstance(final_stage, str) and final_stage.strip():
            text = final_stage.strip()

            if "불합격" in text:
                return "불합격"

            if any(word in text for word in positive_words):
                return "합격"

        if isinstance(offer, str) and offer.strip():
            if "불합격" in offer:
                return "불합격"
            return "합격"

        return "미상"

    df["합격여부"] = df.apply(decide_pass, axis=1)

    return df


# ---------------- 캐시 초기화 버튼 ----------------
if st.sidebar.button("🔄 최신 데이터 다시 불러오기"):
    st.cache_data.clear()
    st.rerun()


# ---------------- 데이터 로딩 ----------------
try:
    df = load_data()

    # 혹시 같은 이름의 컬럼이 중복 생성되었을 경우 첫 번째 컬럼만 남김
    df = df.loc[:, ~df.columns.duplicated()].copy()

except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()


# ---------------- 사이드바: 검색 조건 ----------------
st.sidebar.header("검색 조건")

# 졸업연도 범위
if "졸업년도" in df.columns:
    year_series = pd.to_numeric(df["졸업년도"], errors="coerce")

    if year_series.notna().any():
        min_year = int(year_series.min())
        max_year = int(year_series.max())

        year_range = st.sidebar.slider(
            "졸업연도 범위",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            step=1,
        )
    else:
        year_range = None
        st.sidebar.warning("졸업년도 값이 비어 있습니다.")
else:
    year_range = None
    st.sidebar.warning("졸업년도 컬럼을 찾을 수 없습니다.")

# 출신 중학교
# 여러 중학교를 선택할 수 있도록 multiselect로 변경
if "출신중" in df.columns:
    middle_options = sorted(df["출신중"].dropna().astype(str).unique().tolist())

    selected_middles = st.sidebar.multiselect(
        "출신 중학교",
        options=middle_options,
        default=[],
        help="선택하지 않으면 전체 중학교를 보여줍니다. 여러 중학교를 동시에 선택할 수 있습니다.",
    )
else:
    selected_middles = []

# 대표대학 필터
if "대표대학" in df.columns:
    uni_counts = df["대표대학"].replace("", pd.NA).dropna().value_counts()
    university_options = uni_counts.index.tolist()

    selected_universities = st.sidebar.multiselect(
        "대표 대학",
        options=university_options,
        default=[],
        help="선택하지 않으면 전체 대학을 보여줍니다. 특정 대학만 보고 싶을 때 선택하세요.",
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

# 중학교 내신
if "중학교내신" in df.columns and df["중학교내신"].notna().any():
    min_middle_grade = float(df["중학교내신"].min())
    max_middle_grade = float(df["중학교내신"].max())

    middle_grade_range = st.sidebar.slider(
        "중학교 내신성적 범위",
        min_value=round(min_middle_grade, 1),
        max_value=round(max_middle_grade, 1),
        value=(round(min_middle_grade, 1), round(max_middle_grade, 1)),
        step=0.1,
    )
else:
    middle_grade_range = None

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
    placeholder="예: 경북대, 간호, 교대, 농어촌, 정시",
)

# 대학/전형 그룹 필터
st.sidebar.markdown("### 대학/전형 그룹 필터")
group_filter = st.sidebar.multiselect(
    "아래 그룹 중 포함하고 싶은 것 선택",
    options=["수도권대학", "국립대학", "의치약한수", "간호", "교대", "농어촌"],
)


# ---------------- 필터 적용 ----------------
filtered = df.copy()

# 졸업연도
if year_range and "졸업년도" in filtered.columns:
    filtered = filtered[
        (filtered["졸업년도"] >= year_range[0]) &
        (filtered["졸업년도"] <= year_range[1])
    ]

# 출신중
# 선택한 중학교가 있을 때만 필터링
if selected_middles and "출신중" in filtered.columns:
    filtered = filtered[filtered["출신중"].astype(str).isin(selected_middles)]

# 대표대학
if selected_universities and "대표대학" in filtered.columns:
    filtered = filtered[filtered["대표대학"].isin(selected_universities)]

# 고교 내신
if grade_range and "고교내신" in filtered.columns:
    filtered = filtered[
        (filtered["고교내신"] >= grade_range[0]) &
        (filtered["고교내신"] <= grade_range[1])
    ]

# 중학교 내신
if middle_grade_range and "중학교내신" in filtered.columns:
    filtered = filtered[
        (filtered["중학교내신"] >= middle_grade_range[0]) &
        (filtered["중학교내신"] <= middle_grade_range[1])
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
        "최종단계",
    ]

    available_search_cols = [col for col in search_cols if col in filtered.columns]

    if available_search_cols:
        mask = pd.Series(False, index=filtered.index)

        for col in available_search_cols:
            mask = mask | filtered[col].fillna("").astype(str).str.contains(
                keyword,
                case=False,
                na=False,
                regex=False
            )

        filtered = filtered[mask]

# 대학/전형 그룹 필터
if group_filter:
    mask = pd.Series(False, index=filtered.index)

    for g in group_filter:
        if g in filtered.columns:
            mask = mask | (filtered[g] == True)

    filtered = filtered[mask]


# ---------------- 메인 영역 ----------------
st.subheader("검색 결과 요약")
st.write(f"조건에 해당하는 학생 수: **{len(filtered)}명**")

base_display_cols = [
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
    "최종단계",
    "합격여부",
]

display_cols = [
    col for col in base_display_cols
    if col in filtered.columns and has_visible_values(filtered, col)
]

if display_cols:
    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)
else:
    st.dataframe(filtered, use_container_width=True, hide_index=True)


tab1, tab2, tab3, tab4 = st.tabs(
    ["대학별 합격자", "연도별 합격 추세", "중학교·전형·내신", "의대/간호/교대 분석"]
)


# ---------------- 탭 1: 대학별 합격자 ----------------
with tab1:
    st.markdown("### 대학별 합격자 인원 비교")

    df_uni = filtered[filtered["합격여부"] == "합격"].copy()

    if df_uni.empty:
        st.info("현재 필터 조건에서 합격 데이터가 없습니다.")
    else:
        uni_count = (
            df_uni[df_uni["대표대학"] != ""]
            .groupby("대표대학")["성명"]
            .count()
            .reset_index(name="합격자수")
            .sort_values("합격자수", ascending=False)
        )

        if uni_count.empty:
            st.info("대표대학을 인식한 데이터가 없습니다.")
        else:
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
            st.dataframe(uni_count, use_container_width=True, hide_index=True)


# ---------------- 탭 2: 연도별 합격 추세 ----------------
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
        st.dataframe(trend, use_container_width=True, hide_index=True)

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
        st.dataframe(trend_type, use_container_width=True, hide_index=True)


# ---------------- 탭 3: 중학교·전형·내신 ----------------
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
                .sort_values("평균내신")
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
            st.dataframe(pivot, use_container_width=True, hide_index=True)
    else:
        st.info("출신중 정보가 없습니다.")


# ---------------- 탭 4: 의대/간호/교대 분석 ----------------
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

    st.markdown("#### 의치약한수 합격자")
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
        st.dataframe(med_df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("의치약한수 합격 데이터가 없습니다.")

    st.markdown("#### 간호 계열 합격자")
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
        st.dataframe(nur_df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("간호 계열 합격 데이터가 없습니다.")

    st.markdown("#### 교대 합격자")
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
        st.dataframe(tch_df[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("교대 합격 데이터가 없습니다.")


# ---------------- 화면 좌측 하단 만든이 표시 ----------------
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
