# -*- coding: utf-8 -*-
"""
함창고 입시결과 검색 · 시각화 대시보드 v3
- 다중 합격(한 학생 여러 대학) explode 처리
- 학과 계열 분류 우선순위 개선(사범계열 과목명 우선 판정)
- 대학명 정규화 캠퍼스 보존 옵션
- 슬라이더 min==max 방어
- 탭별 표시 컬럼 재계산
- 합격여부 판정 보수화 + 결과확정 플래그
- 성명 마스킹 토글
- 파란색/흰색 기반 전문 교육용 디자인 + 애니메이션
"""

import re
import csv

import streamlit as st
import pandas as pd
import altair as alt


# ==================================================================
# 기본 설정
# ==================================================================
st.set_page_config(
    page_title="함창고 입시결과 대시보드",
    page_icon="\U0001F393",
    layout="wide",
)


# ==================================================================
# 시각 디자인 (파란색 · 흰색 테마 + 애니메이션)
# ==================================================================
BLUE_DARK = "#1e40af"
BLUE_MAIN = "#2563eb"
BLUE_SOFT = "#60a5fa"
BLUE_PALE = "#dbeafe"

CUSTOM_CSS = f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

html, body, [class*="css"] {{
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}}

.stApp {{
    background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
}}

.hero-banner {{
    background: linear-gradient(120deg, {BLUE_DARK} 0%, {BLUE_MAIN} 60%, {BLUE_SOFT} 100%);
    color: #ffffff;
    padding: 26px 32px;
    border-radius: 18px;
    margin-bottom: 8px;
    box-shadow: 0 10px 30px rgba(37, 99, 235, 0.25);
    animation: fadeInDown 0.7s ease both;
}}
.hero-banner h1 {{ font-size: 1.9rem; font-weight: 800; margin: 0; letter-spacing: -0.5px; }}
.hero-banner p {{ margin: 8px 0 0 0; font-size: 0.95rem; opacity: 0.92; }}

.metric-card {{
    background: #ffffff;
    border: 1px solid {BLUE_PALE};
    border-top: 4px solid {BLUE_MAIN};
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 6px 18px rgba(30, 64, 175, 0.08);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    animation: fadeInUp 0.6s ease both;
}}
.metric-card:hover {{ transform: translateY(-4px); box-shadow: 0 12px 28px rgba(30, 64, 175, 0.18); }}
.metric-card .label {{ font-size: 0.85rem; color: #64748b; font-weight: 600; margin-bottom: 6px; }}
.metric-card .value {{ font-size: 2.0rem; font-weight: 800; color: {BLUE_DARK}; line-height: 1.1; }}
.metric-card .unit {{ font-size: 0.9rem; color: #94a3b8; margin-left: 4px; }}

.section-title {{
    font-size: 1.15rem; font-weight: 800; color: {BLUE_DARK};
    border-left: 5px solid {BLUE_MAIN}; padding-left: 12px; margin: 6px 0 14px 0;
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; background: #ffffff; padding: 6px; border-radius: 12px; border: 1px solid {BLUE_PALE};
}}
.stTabs [data-baseweb="tab"] {{ border-radius: 8px; padding: 8px 16px; font-weight: 600; color: #475569; }}
.stTabs [aria-selected="true"] {{ background: {BLUE_MAIN}; color: #ffffff !important; }}

section[data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid {BLUE_PALE}; }}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{ color: {BLUE_DARK}; }}

.stButton > button {{
    background: {BLUE_MAIN}; color: #ffffff; border: none; border-radius: 10px;
    font-weight: 700; transition: background 0.2s ease, transform 0.1s ease;
}}
.stButton > button:hover {{ background: {BLUE_DARK}; transform: translateY(-1px); }}

[data-testid="stDataFrame"] {{
    border-radius: 12px; overflow: hidden; border: 1px solid {BLUE_PALE}; animation: fadeIn 0.6s ease both;
}}

@keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes fadeInDown {{ from {{ opacity: 0; transform: translateY(-16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero-banner">
        <h1>\U0001F393 함창고 입시결과 검색 · 시각화 대시보드</h1>
        <p>내부 참고용 · 상담 활용 시 학생 개인정보는 가급적 숨기고 활용하시기 바랍니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==================================================================
# Altair 커스텀 테마
# ==================================================================
def blue_theme():
    return {
        "config": {
            "view": {"stroke": "transparent"},
            "background": "white",
            "font": "Pretendard",
            "axis": {
                "labelColor": "#334155", "titleColor": "#1e40af",
                "labelFontSize": 12, "titleFontSize": 13, "titleFontWeight": 700,
                "grid": True, "gridColor": "#eef2ff",
                "domainColor": "#cbd5e1", "tickColor": "#cbd5e1",
            },
            "legend": {"labelColor": "#334155", "titleColor": "#1e40af", "titleFontWeight": 700},
            "range": {
                "category": ["#2563eb", "#60a5fa", "#1e40af", "#93c5fd",
                             "#3b82f6", "#1d4ed8", "#bfdbfe", "#0ea5e9"],
                "heatmap": ["#eff6ff", "#2563eb"],
            },
            "title": {"color": "#1e40af", "fontSize": 15, "fontWeight": 800},
        }
    }


alt.themes.register("blue_theme", blue_theme)
alt.themes.enable("blue_theme")

BAR_COLOR = BLUE_MAIN


# ==================================================================
# 유틸 함수
# ==================================================================
def normalize_col_name(col):
    text = str(col)
    text = text.replace("\ufeff", "").replace("\xa0", "")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def first_existing_column(df, candidates):
    normalized_map = {normalize_col_name(c): c for c in df.columns}
    for cand in candidates:
        key = normalize_col_name(cand)
        if key in normalized_map:
            return normalized_map[key]
    return None


def get_series(df, col, default=""):
    if col is None or col not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    value = df[col]
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def safe_to_numeric(series):
    def parse_one(x):
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan"):
            return None
        m = re.match(r"^\s*(\d+\.?\d*)\s*[~\-/]\s*(\d+\.?\d*)\s*$", s)
        if m:
            try:
                return (float(m.group(1)) + float(m.group(2))) / 2.0
            except ValueError:
                return None
        m2 = re.search(r"(\d+\.?\d*)", s)
        if m2:
            try:
                return float(m2.group(1))
            except ValueError:
                return None
        return None
    return pd.to_numeric(series.apply(parse_one), errors="coerce")


def has_visible_values(df, col):
    if col not in df.columns:
        return False
    s = df[col].fillna("").astype(str).str.strip()
    s = s[~s.str.lower().isin(["", "none", "nan"])]
    return len(s) > 0


def visible_display_cols(df, base_cols):
    return [c for c in base_cols if c in df.columns and has_visible_values(df, c)]


def mask_name(name):
    if not isinstance(name, str):
        return name
    s = name.strip()
    if len(s) <= 1:
        return s
    if len(s) == 2:
        return s[0] + "\u25CB"
    return s[0] + "\u25CB" * (len(s) - 2) + s[-1]


# ==================================================================
# CSV 읽기
# ==================================================================
def read_admission_file(file_path):
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

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{file_path} 파일이 비어 있습니다.")

    header_idx = None
    for i, line in enumerate(lines):
        compact = (line.replace(" ", "").replace("\t", "")
                   .replace(",", "").replace(";", "").replace("|", ""))
        if ("졸업년도" in compact or "졸업연도" in compact) and "성명" in compact:
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("실제 헤더 행을 찾지 못했습니다. '졸업년도'와 '성명'이 든 헤더 행이 있는지 확인해 주세요.")

    header_line = lines[header_idx]
    data_lines = lines[header_idx + 1:]

    delimiter_candidates = ["\t", ",", ";", "|"]
    delimiter = max(delimiter_candidates, key=lambda d: header_line.count(d))
    if header_line.count(delimiter) == 0:
        raise ValueError("헤더 행에서 구분자를 찾지 못했습니다. CSV UTF-8 또는 탭 구분으로 다시 저장해 주세요.")

    try:
        headers = next(csv.reader([header_line], delimiter=delimiter))
    except Exception:
        headers = header_line.split(delimiter)

    headers = [str(h).replace("\ufeff", "").replace("\n", "").replace("\r", "")
               .strip().strip('"').strip("'") for h in headers]
    headers = [h if h else f"빈컬럼{i + 1}" for i, h in enumerate(headers)]

    col_count = len(headers)
    if col_count <= 1:
        raise ValueError("컬럼이 1개로만 인식되었습니다. 헤더 구분자를 확인해 주세요.")

    rows = []
    reader = csv.reader(data_lines, delimiter=delimiter)
    for parts in reader:
        if not parts:
            continue
        if len(parts) == 1 and not str(parts[0]).strip():
            continue
        if len(parts) < col_count:
            parts = parts + [""] * (col_count - len(parts))
        elif len(parts) > col_count:
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
    df.columns = (df.columns.astype(str)
                  .str.replace("\ufeff", "", regex=False)
                  .str.replace("\n", "", regex=False)
                  .str.replace("\r", "", regex=False)
                  .str.strip())
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df.attrs["read_info"] = f"{used_encoding} / 헤더 {header_idx + 1}행 / 구분자 {repr(delimiter)}"
    return df


def find_offer_column(df):
    candidates = ["주요 합격 대학/전형/학과", "주요합격대학/전형/학과", "주요합격",
                  "합격대학/전형/학과", "대학/전형/학과", "주요 합격",
                  "주요합격대학전형학과", "주요합격대학"]
    found = first_existing_column(df, candidates)
    if found:
        return found
    for c in df.columns:
        compact = normalize_col_name(c)
        if "합격" in compact and ("대학" in compact or "전형" in compact or "학과" in compact):
            return c
    known_cols = {"졸업년도", "졸업연도", "출신중", "출신중학교", "성명", "이름", "학생명",
                  "내신(중)", "중학교내신", "중학교내신성적", "내신(고)", "고교내신",
                  "고등학교내신", "고입석차", "고등학교석차", "고등학교 석차"}
    known_normalized = {normalize_col_name(x) for x in known_cols}
    best_col, best_score = None, -1
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
            best_score, best_col = score, c
    return best_col if best_score > 0 else None


def repair_offer_and_high_rank(df):
    if "주요합격" not in df.columns:
        return df
    if "고등학교석차" not in df.columns:
        df["고등학교석차"] = None
    offer_text = df["주요합격"].fillna("").astype(str)
    extracted = offer_text.str.extract(r'^\s*"?(\d+)\s*[;,]\s*"?(.+)$')
    mask = extracted[0].notna() & extracted[1].notna()
    high_rank_empty = (df["고등학교석차"].isna()
                       | (df["고등학교석차"].astype(str).str.strip() == "")
                       | (df["고등학교석차"].astype(str).str.strip().str.lower() == "none")
                       | (df["고등학교석차"].astype(str).str.strip().str.lower() == "nan"))
    df.loc[mask & high_rank_empty, "고등학교석차"] = extracted.loc[mask & high_rank_empty, 0]
    df.loc[mask, "주요합격"] = extracted.loc[mask, 1]
    df["주요합격"] = (df["주요합격"].fillna("").astype(str).str.strip()
                   .str.strip('"').str.strip("'").str.replace('""', '"', regex=False))
    return df


# ==================================================================
# 다중 합격 분리
# ==================================================================
def split_offer_entries(text):
    if not isinstance(text, str):
        return []
    text = text.strip()
    if not text:
        return []
    rough = re.split(r"[\n;]+", text)
    entries = []
    for chunk in rough:
        chunk = chunk.strip()
        if not chunk:
            continue
        comma_parts = [p.strip() for p in chunk.split(",") if p.strip()]
        offer_like = [p for p in comma_parts if ("/" in p or " - " in p or "-" in p)]
        if len(comma_parts) >= 2 and len(offer_like) >= 2:
            entries.extend(comma_parts)
        else:
            entries.append(chunk)
    return entries if entries else [text]


def parse_offer_entry(text):
    result = {"대표대학": "", "전형유형원문": "", "대표학과": ""}
    if not isinstance(text, str):
        return result
    first = text.strip().strip('"').strip("'")
    if not first:
        return result
    first = re.sub(r'^\s*\d+\s*[;,]\s*"?', "", first).strip().strip('"').strip("'")
    if "/" in first:
        parts = [p.strip() for p in first.split("/")]
    elif " - " in first:
        parts = [p.strip() for p in first.split(" - ")]
    elif "-" in first:
        parts = [p.strip() for p in first.split("-")]
    else:
        parts = [first]
    if len(parts) >= 1:
        result["대표대학"] = parts[0].split("(")[0].strip()
    if len(parts) >= 2:
        result["전형유형원문"] = parts[1].strip()
    else:
        result["전형유형원문"] = first
    if len(parts) >= 3:
        result["대표학과"] = parts[2].strip()
    return result


# ==================================================================
# 분류 함수
# ==================================================================
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


def classify_major_group(major):
    if not isinstance(major, str):
        return "기타"
    text = major.replace(" ", "").strip()
    if not text:
        return "기타"
    if any(k in text for k in ["의학", "의예", "치의", "약학", "한의", "수의", "간호",
                               "보건", "물리치료", "임상병리", "방사선", "치위생"]):
        return "의학/보건계열"
    edu_markers = ["교육과", "교육학과", "교육대", "사범", "초등교육", "유아교육", "특수교육"]
    if any(k in text for k in edu_markers) or text.endswith("교육"):
        return "인문/사회계열(사범 포함)"
    if any(k in text for k in ["체육", "스포츠", "음악", "미술", "디자인", "무용", "연극",
                               "영화", "영상", "패션", "뷰티", "실용음악", "만화", "애니"]):
        return "예체능계열"
    if any(k in text for k in ["기계", "전기", "전자", "화학", "컴퓨터", "소프트웨어", "공학",
                               "건축", "토목", "환경", "AI", "인공지능", "정보", "데이터",
                               "반도체", "로봇", "자동차", "에너지", "수학", "물리", "생명",
                               "생물", "통계", "산업", "재료", "신소재", "항공"]):
        return "공학/이공계열"
    if any(k in text for k in ["국어", "영어", "경영", "경제", "행정", "심리", "사회", "문헌",
                               "복지", "법", "정치", "언론", "미디어", "역사", "철학", "문화",
                               "관광", "국제", "무역", "회계", "세무"]):
        return "인문/사회계열"
    return "기타"


def normalize_university_name(name, keep_campus=False):
    if not isinstance(name, str):
        return ""
    campus = ""
    if keep_campus:
        m = re.search(r"\(([^)]*)\)", name)
        if m:
            campus = f"({m.group(1).strip()})"
    text = name.replace(" ", "").replace("\u3000", "")
    for c in ["(서울)", "(경산)", "(대구)", "(경북)", "(부산)", "(천안)", "(글로벌)", "(제2)", "(분교)"]:
        text = text.replace(c, "")
    text = text.strip()
    alias_map = {
        "서울대": "서울대학교", "연세대": "연세대학교", "고려대": "고려대학교",
        "서강대": "서강대학교", "성균관대": "성균관대학교", "한양대": "한양대학교",
        "중앙대": "중앙대학교", "경희대": "경희대학교", "한국외대": "한국외국어대학교",
        "외대": "한국외국어대학교", "서울시립대": "서울시립대학교", "시립대": "서울시립대학교",
        "건국대": "건국대학교", "동국대": "동국대학교", "홍익대": "홍익대학교", "숭실대": "숭실대학교",
        "경북대": "경북대학교", "부산대": "부산대학교", "전남대": "전남대학교", "전북대": "전북대학교",
        "충남대": "충남대학교", "충북대": "충북대학교", "강원대": "강원대학교", "제주대": "제주대학교",
        "경상국립대": "경상국립대학교", "금오공대": "금오공과대학교", "금오공과대": "금오공과대학교",
        "서울과기대": "서울과학기술대학교", "서울과학기술대": "서울과학기술대학교",
        "교통대": "한국교통대학교", "한국교통대": "한국교통대학교", "군산대": "군산대학교",
        "공주대": "공주대학교", "안동대": "안동대학교", "창원대": "창원대학교", "부경대": "부경대학교",
        "한국해양대": "한국해양대학교", "목포대": "목포대학교", "순천대": "순천대학교",
        "한국교원대": "한국교원대학교", "한국체대": "한국체육대학교", "한국체육대": "한국체육대학교",
        "영남대": "영남대학교", "계명대": "계명대학교", "대구대": "대구대학교",
        "대구가톨릭대": "대구가톨릭대학교", "대가대": "대구가톨릭대학교", "대구한의대": "대구한의대학교",
        "동국대WISE": "동국대학교WISE캠퍼스", "동국대와이즈": "동국대학교WISE캠퍼스",
        "동양대": "동양대학교", "경운대": "경운대학교", "위덕대": "위덕대학교", "김천대": "김천대학교",
        "대구교대": "대구교육대학교", "부산교대": "부산교육대학교", "서울교대": "서울교육대학교",
        "경인교대": "경인교육대학교", "청주교대": "청주교육대학교", "공주교대": "공주교육대학교",
        "전주교대": "전주교육대학교", "진주교대": "진주교육대학교", "춘천교대": "춘천교육대학교",
        "광주교대": "광주교육대학교", "제주교대": "제주교육대학교",
    }
    if text in alias_map:
        base = alias_map[text]
    elif text.endswith("대학교"):
        base = text
    elif text.endswith("교육대"):
        base = text + "학교"
    elif text.endswith("교대"):
        base = text
    elif text.endswith("대") and len(text) >= 3:
        base = text[:-1] + "대학교"
    else:
        base = text
    return f"{base}{campus}" if keep_campus and campus else base


MED_KEYWORDS = ["의예", "의학", "의학부", "치의", "치의예", "치의학", "약학", "신약",
                "한의", "한의예", "한의학", "한의약", "수의", "수의예", "수의학"]


def is_med_major(major):
    if not isinstance(major, str):
        return False
    return any(k in major.replace(" ", "").strip() for k in MED_KEYWORDS)


def is_nursing_major(major):
    return isinstance(major, str) and "간호" in major.replace(" ", "")


def is_med_school(major):
    if not isinstance(major, str):
        return False
    text = major.replace(" ", "").strip()
    return (any(k in text for k in ["의예", "의학", "의학부"])
            and not any(k in text for k in ["치의", "한의", "수의"]))


def is_dent_school(major):
    text = major.replace(" ", "").strip() if isinstance(major, str) else ""
    return any(k in text for k in ["치의", "치의예", "치의학"])


def is_pharm_school(major):
    text = major.replace(" ", "").strip() if isinstance(major, str) else ""
    return any(k in text for k in ["약학", "신약"])


def is_korean_med_school(major):
    text = major.replace(" ", "").strip() if isinstance(major, str) else ""
    return any(k in text for k in ["한의", "한의예", "한의학", "한의약"])


def is_vet_school(major):
    text = major.replace(" ", "").strip() if isinstance(major, str) else ""
    return any(k in text for k in ["수의", "수의예", "수의학"])


def is_teacher_univ(name):
    if not isinstance(name, str):
        return False
    text = name.replace(" ", "").strip()
    return ("교대" in text) or ("교육대" in text)


def contains_rural(text):
    return isinstance(text, str) and "농어촌" in text


# ==================================================================
# 데이터 로딩 + 전처리 (event-level explode)
# ==================================================================
@st.cache_data
def load_data(keep_campus=False):
    df = read_admission_file("admission_results.csv")
    if df is None:
        raise ValueError("데이터 파일을 읽지 못했습니다.")
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df.columns = (df.columns.astype(str)
                  .str.replace("\ufeff", "", regex=False)
                  .str.replace("\n", "", regex=False)
                  .str.replace("\r", "", regex=False)
                  .str.strip())

    col_graduation = first_existing_column(df, ["졸업년도", "졸업연도"])
    col_middle = first_existing_column(df, ["출신중", "출신중학교"])
    col_name = first_existing_column(df, ["성명", "이름", "학생명"])
    col_middle_grade = first_existing_column(df, ["내신(중)", "중학교내신", "중학교 내신", "중학교내신성적", "중학교 내신성적"])
    col_high_grade = first_existing_column(df, ["내신(고)", "고교내신", "고교 내신", "고등학교내신", "고등학교 내신"])
    col_middle_rank = first_existing_column(df, ["고입석차", "고입 석차"])
    col_high_rank = first_existing_column(df, ["고등학교석차", "고등학교 석차", "고등학교\n석차", "고등학교서차"])
    col_offer = find_offer_column(df)
    col_final_stage = first_existing_column(df, ["최종단계", "최종 단계", "최종결과", "합격결과"])
    col_admission_name = first_existing_column(df, ["전형명", "세부전형명", "전형 이름"])
    col_admission_method = first_existing_column(df, ["전형방법", "전형 방법", "방법"])

    df["졸업년도"] = get_series(df, col_graduation, None)
    df["출신중"] = get_series(df, col_middle, "")
    df["성명"] = get_series(df, col_name, "")
    df["중학교내신"] = get_series(df, col_middle_grade, "")
    df["고교내신"] = get_series(df, col_high_grade, "")
    df["고입석차"] = get_series(df, col_middle_rank, "")
    df["고등학교석차"] = get_series(df, col_high_rank, "")
    df["주요합격"] = get_series(df, col_offer, "")
    df["최종단계"] = get_series(df, col_final_stage, "")
    df["전형명"] = get_series(df, col_admission_name, "")
    df["전형방법"] = get_series(df, col_admission_method, "")

    df = repair_offer_and_high_rank(df)

    for col in ["졸업년도", "중학교내신", "고교내신", "고입석차", "고등학교석차"]:
        df[col] = safe_to_numeric(df[col])

    df = df[df["졸업년도"].notna()].copy()
    df = df[(df["졸업년도"] >= 2000) & (df["졸업년도"] <= 2100)].copy()
    if df.empty:
        raise ValueError("졸업년도 데이터를 찾지 못했습니다. 컬럼명을 확인해 주세요.")
    df["졸업년도"] = df["졸업년도"].astype(int)

    df = df.reset_index(drop=True)
    df["학생키"] = (df["졸업년도"].astype(str) + "|" + df["출신중"].astype(str) + "|"
                 + df["성명"].astype(str) + "|" + df.index.astype(str))

    df["합격항목목록"] = df["주요합격"].fillna("").astype(str).apply(split_offer_entries)
    df["합격건수"] = df["합격항목목록"].apply(len).clip(lower=1)

    ev = df.explode("합격항목목록", ignore_index=True)
    ev["합격항목"] = ev["합격항목목록"].fillna("").astype(str)
    ev = ev.drop(columns=["합격항목목록"])

    parsed = ev["합격항목"].apply(parse_offer_entry).apply(pd.Series)
    for col in ["대표대학", "전형유형원문", "대표학과"]:
        if col in ev.columns:
            ev = ev.drop(columns=[col])
    ev = pd.concat([ev, parsed[["대표대학", "전형유형원문", "대표학과"]]], axis=1)
    for col in ["대표대학", "전형유형원문", "대표학과"]:
        ev[col] = ev[col].fillna("").astype(str)

    ev["전형대분류"] = ev["전형유형원문"].apply(classify_type)
    ev["학과계열"] = ev["대표학과"].apply(classify_major_group)
    ev["대표대학정규화"] = ev["대표대학"].apply(lambda x: normalize_university_name(x, keep_campus=keep_campus))
    ev["대표대학"] = ev["대표대학정규화"]

    ev["교대"] = ev["대표대학"].apply(is_teacher_univ)
    ev["의치약한수"] = ev["대표학과"].apply(is_med_major)
    ev["간호"] = ev["대표학과"].apply(is_nursing_major)
    ev["의대"] = ev["대표학과"].apply(is_med_school)
    ev["치대"] = ev["대표학과"].apply(is_dent_school)
    ev["약대"] = ev["대표학과"].apply(is_pharm_school)
    ev["한의대"] = ev["대표학과"].apply(is_korean_med_school)
    ev["수의대"] = ev["대표학과"].apply(is_vet_school)

    CAPITAL = ["서울대", "연세대", "고려대", "서강대", "성균관대", "한양대", "중앙대", "경희대",
               "한국외대", "서울시립대", "건국대", "동국대", "홍익대", "숭실대"]
    NATIONAL = ["경북대", "부산대", "전남대", "전북대", "충남대", "충북대", "강원대", "제주대",
                "경상국립대", "금오공대", "서울과기대", "교통대", "군산대", "공주대", "안동대",
                "창원대", "부경대", "한국해양대", "목포대", "순천대", "한국교원대", "한국체대"]
    capital_set = {normalize_university_name(x) for x in CAPITAL}
    national_set = {normalize_university_name(x) for x in NATIONAL}
    base_norm = ev["대표대학"].apply(lambda x: normalize_university_name(x, keep_campus=False))
    ev["수도권대학"] = base_norm.isin(capital_set)
    ev["국립대학"] = base_norm.isin(national_set)

    ev["농어촌"] = ev.apply(
        lambda r: (contains_rural(r.get("전형유형원문", "")) or contains_rural(r.get("주요합격", ""))
                   or contains_rural(r.get("전형명", "")) or contains_rural(r.get("전형방법", ""))),
        axis=1)

    positive_words = ["최초합격", "충원합격", "추가합격", "추합", "최종합격", "합격", "등록"]
    negative_markers = ["불합격", "미등록", "미충원", "예비", "지원", "미정", "탈락"]

    def decide_pass(row):
        final_stage = str(row.get("최종단계", "") or "").strip()
        offer = str(row.get("합격항목", "") or "").strip()
        if final_stage:
            if "불합격" in final_stage:
                return "불합격", True
            if any(w in final_stage for w in positive_words):
                return "합격", True
            return "미상", False
        if offer:
            if any(n in offer for n in negative_markers):
                return "미상", False
            return "합격", False
        return "미상", False

    decided = ev.apply(decide_pass, axis=1, result_type="expand")
    ev["합격여부"] = decided[0]
    ev["결과확정"] = decided[1]
    ev["성명원본"] = ev["성명"]
    return ev


# ==================================================================
# 사이드바 — 옵션
# ==================================================================
st.sidebar.header("\u2699\uFE0F 표시 옵션")

keep_campus = st.sidebar.checkbox("대학 캠퍼스 구분 유지", value=False,
                                  help="체크하면 (경산)/(글로벌) 등 캠퍼스 표기를 유지합니다.")
mask_names = st.sidebar.checkbox("성명 마스킹", value=True,
                                 help="상담 화면 노출 시 개인정보 보호를 위해 성명을 가립니다.")
count_mode = st.sidebar.radio("집계 기준", ["합격 건수", "학생 수"], index=0,
                              help="한 학생이 여러 대학에 합격한 경우 집계 방식을 선택합니다.")

if st.sidebar.button("\U0001F504 최신 데이터 다시 불러오기"):
    st.cache_data.clear()
    st.rerun()


# ==================================================================
# 데이터 로딩
# ==================================================================
try:
    df = load_data(keep_campus=keep_campus)
    if df is None:
        raise ValueError("load_data()가 데이터를 반환하지 못했습니다.")
    df = df.loc[:, ~df.columns.duplicated()].copy()
except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()

df["성명표시"] = df["성명원본"].apply(mask_name) if mask_names else df["성명원본"]


def count_agg(frame, group_cols):
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    g = frame.groupby(group_cols)
    if count_mode == "학생 수":
        return g["학생키"].nunique().reset_index(name="합격자수")
    return g.size().reset_index(name="합격자수")


# ==================================================================
# 사이드바 — 검색 조건
# ==================================================================
st.sidebar.header("\U0001F50D 검색 조건")


def safe_slider(label, series, step, decimals=0):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    lo, hi = float(s.min()), float(s.max())
    if decimals > 0:
        lo, hi = round(lo, decimals), round(hi, decimals)
    else:
        lo, hi = int(lo), int(hi)
    if lo == hi:
        st.sidebar.caption(f"{label}: {lo} (단일 값)")
        return (lo, hi)
    return st.sidebar.slider(label, min_value=lo, max_value=hi, value=(lo, hi), step=step)


year_range = safe_slider("졸업연도 범위", df["졸업년도"], step=1, decimals=0)

middle_options = sorted(df["출신중"].dropna().astype(str).unique().tolist())
selected_middles = st.sidebar.multiselect("출신 중학교", options=middle_options, default=[])

uni_counts = df["대표대학"].replace("", pd.NA).dropna().value_counts()
selected_universities = st.sidebar.multiselect("대표 대학", options=uni_counts.index.tolist(), default=[])

grade_range = safe_slider("고교 내신 등급 범위", df["고교내신"], step=0.1, decimals=1)
middle_grade_range = safe_slider("중학교 내신성적 범위", df["중학교내신"], step=0.1, decimals=1)

type_options = ["전체"] + sorted(df["전형대분류"].dropna().astype(str).unique().tolist())
selected_type = st.sidebar.selectbox("전형 대분류", type_options)

major_group_options = ["전체"] + sorted(df["학과계열"].dropna().astype(str).unique().tolist())
selected_major_group = st.sidebar.selectbox("학과 계열", major_group_options)

med_view_option = st.sidebar.selectbox(
    "의치약한수 분류 필터",
    ["제한 없음", "의치약한수만(전체)", "의대만", "치대만", "약대만", "한의대만", "수의대만"])

keyword = st.sidebar.text_input("대학/전형/학과 키워드", value="",
                                placeholder="예: 경북대, 간호, 교대, 농어촌, 정시")

st.sidebar.markdown("### 대학/전형 그룹 필터")
group_filter = st.sidebar.multiselect(
    "포함할 그룹 선택",
    options=["수도권대학", "국립대학", "의치약한수", "간호", "교대", "농어촌"])

only_confirmed = st.sidebar.checkbox("결과확정 데이터만 보기", value=False,
                                     help="최종단계에 합격/불합격이 명시된 행만 표시합니다.")


# ==================================================================
# 필터 적용
# ==================================================================
filtered = df.copy()

if year_range:
    filtered = filtered[(filtered["졸업년도"] >= year_range[0]) & (filtered["졸업년도"] <= year_range[1])]
if selected_middles:
    filtered = filtered[filtered["출신중"].astype(str).isin(selected_middles)]
if selected_universities:
    filtered = filtered[filtered["대표대학"].isin(selected_universities)]
if grade_range:
    filtered = filtered[(filtered["고교내신"] >= grade_range[0]) & (filtered["고교내신"] <= grade_range[1])]
if middle_grade_range:
    filtered = filtered[(filtered["중학교내신"] >= middle_grade_range[0]) & (filtered["중학교내신"] <= middle_grade_range[1])]
if selected_type != "전체":
    filtered = filtered[filtered["전형대분류"] == selected_type]
if selected_major_group != "전체":
    filtered = filtered[filtered["학과계열"] == selected_major_group]

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

if keyword:
    keyword = keyword.strip()
    search_cols = ["주요합격", "합격항목", "대표대학", "전형유형원문", "대표학과", "전형명", "전형방법", "최종단계"]
    available = [c for c in search_cols if c in filtered.columns]
    if available:
        mask = pd.Series(False, index=filtered.index)
        for col in available:
            mask = mask | filtered[col].fillna("").astype(str).str.contains(keyword, case=False, na=False, regex=False)
        filtered = filtered[mask]

if group_filter:
    mask = pd.Series(False, index=filtered.index)
    for g in group_filter:
        if g in filtered.columns:
            mask = mask | (filtered[g] == True)
    filtered = filtered[mask]

if only_confirmed:
    filtered = filtered[filtered["결과확정"] == True]


# ==================================================================
# 상단 요약 지표 카드
# ==================================================================
pass_df = filtered[filtered["합격여부"] == "합격"]
n_students = filtered["학생키"].nunique()
n_offers = len(filtered)
n_pass = len(pass_df)
n_uni = pass_df[pass_df["대표대학"] != ""]["대표대학"].nunique()

c1, c2, c3, c4 = st.columns(4)
cards = [
    (c1, "학생 수", f"{n_students:,}", "명"),
    (c2, "합격 건수", f"{n_offers:,}", "건"),
    (c3, "합격 처리", f"{n_pass:,}", "건"),
    (c4, "합격 대학 수", f"{n_uni:,}", "개교"),
]
for col, label, value, unit in cards:
    col.markdown(
        f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="value">{value}<span class="unit">{unit}</span></div>
            </div>""",
        unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ==================================================================
# 검색 결과 표
# ==================================================================
st.markdown('<div class="section-title">검색 결과</div>', unsafe_allow_html=True)

base_display_cols = ["졸업년도", "출신중", "성명표시", "중학교내신", "고입석차", "고교내신",
                     "고등학교석차", "대표대학", "전형유형원문", "대표학과", "전형명", "전형방법",
                     "합격항목", "최종단계", "합격여부"]
rename_map = {"성명표시": "성명", "합격항목": "합격(대학/전형/학과)"}

display_cols = visible_display_cols(filtered, base_display_cols)
if display_cols:
    st.dataframe(filtered[display_cols].rename(columns=rename_map), use_container_width=True, hide_index=True)
else:
    st.dataframe(filtered, use_container_width=True, hide_index=True)


# ==================================================================
# 탭
# ==================================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["\U0001F3EB 대학별 합격자", "\U0001F4C8 연도별 추세", "\U0001F4CA 중학교·전형·내신", "\U0001FA7A 의대/간호/교대"])


def bar_chart(data, x_field, x_title, y_title="합격자수", color_field=None, height=350, sort="-y"):
    enc = {"x": alt.X(f"{x_field}:N", sort=sort, title=x_title),
           "y": alt.Y(f"{y_title}:Q", title=y_title)}
    tooltip = [x_field, y_title]
    if color_field:
        enc["color"] = alt.Color(f"{color_field}:N", title=color_field)
        tooltip = [x_field, color_field, y_title]
    else:
        enc["color"] = alt.value(BAR_COLOR)
    enc["tooltip"] = tooltip
    return (alt.Chart(data).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(**enc).properties(height=height))


def line_chart(data, x_field, x_title, color_field=None, height=320):
    enc = {"x": alt.X(f"{x_field}:O", title=x_title), "y": alt.Y("합격자수:Q", title="합격자수")}
    tooltip = [x_field, "합격자수"]
    if color_field:
        enc["color"] = alt.Color(f"{color_field}:N", title=color_field)
        tooltip = [x_field, color_field, "합격자수"]
    else:
        enc["color"] = alt.value(BAR_COLOR)
    enc["tooltip"] = tooltip
    return (alt.Chart(data).mark_line(point=alt.OverlayMarkDef(size=70, filled=True), strokeWidth=3)
            .encode(**enc).properties(height=height))


with tab1:
    st.markdown('<div class="section-title">대학별 합격자 인원 비교</div>', unsafe_allow_html=True)
    df_uni = pass_df[pass_df["대표대학"] != ""].copy()
    if df_uni.empty:
        st.info("현재 필터 조건에서 합격 데이터가 없습니다.")
    else:
        uni_count = count_agg(df_uni, "대표대학").sort_values("합격자수", ascending=False)
        st.altair_chart(bar_chart(uni_count, "대표대학", "대학"), use_container_width=True)
        st.dataframe(uni_count, use_container_width=True, hide_index=True)


with tab2:
    st.markdown('<div class="section-title">연도별 합격 추세</div>', unsafe_allow_html=True)
    df_year = pass_df.copy()
    if df_year.empty:
        st.info("합격 데이터가 없습니다.")
    else:
        trend = count_agg(df_year, "졸업년도").sort_values("졸업년도")
        st.altair_chart(line_chart(trend, "졸업년도", "졸업년도"), use_container_width=True)
        st.dataframe(trend, use_container_width=True, hide_index=True)
        st.markdown('<div class="section-title">전형 대분류별 연도별 추세</div>', unsafe_allow_html=True)
        trend_type = count_agg(df_year, ["졸업년도", "전형대분류"])
        st.altair_chart(line_chart(trend_type, "졸업년도", "졸업년도", color_field="전형대분류"), use_container_width=True)
        st.dataframe(trend_type, use_container_width=True, hide_index=True)


with tab3:
    st.markdown('<div class="section-title">중학교별 · 전형대분류별 평균 내신 비교</div>', unsafe_allow_html=True)
    if not filtered.empty:
        df_valid = filtered.dropna(subset=["고교내신"])
        if df_valid.empty:
            st.info("내신 정보가 없습니다.")
        else:
            pivot = (df_valid.groupby(["출신중", "전형대분류"])["고교내신"]
                     .mean().reset_index(name="평균내신").sort_values("평균내신"))
            chart_pivot = (alt.Chart(pivot).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                           .encode(x=alt.X("출신중:N", title="출신중"),
                                   y=alt.Y("평균내신:Q", title="평균 내신"),
                                   color=alt.Color("전형대분류:N", title="전형"),
                                   tooltip=["출신중", "전형대분류", alt.Tooltip("평균내신:Q", format=".2f")])
                           .properties(height=350))
            st.altair_chart(chart_pivot, use_container_width=True)
            st.dataframe(pivot, use_container_width=True, hide_index=True)
    else:
        st.info("출신중 정보가 없습니다.")


with tab4:
    st.markdown('<div class="section-title">의대 · 간호 · 교대 진학 분석</div>', unsafe_allow_html=True)
    med_df = pass_df[pass_df["의치약한수"] == True]
    nur_df = pass_df[pass_df["간호"] == True]
    tch_df = pass_df[pass_df["교대"] == True]

    def metric_count(frame):
        return frame["학생키"].nunique() if count_mode == "학생 수" else len(frame)

    m1, m2, m3 = st.columns(3)
    for col, label, frame in [(m1, "의치약한수", med_df), (m2, "간호 계열", nur_df), (m3, "교대", tch_df)]:
        col.markdown(
            f"""<div class="metric-card">
                    <div class="label">{label} 합격</div>
                    <div class="value">{metric_count(frame):,}<span class="unit">건</span></div>
                </div>""",
            unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    def section(title, frame):
        st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
        if frame.empty:
            st.info(f"{title} 데이터가 없습니다.")
            return
        trend = count_agg(frame, "졸업년도").sort_values("졸업년도")
        st.altair_chart(line_chart(trend, "졸업년도", "졸업년도", height=300), use_container_width=True)
        cols = visible_display_cols(frame, base_display_cols)
        st.dataframe(frame[cols].rename(columns=rename_map) if cols else frame,
                     use_container_width=True, hide_index=True)

    section("의치약한수 합격자", med_df)
    section("간호 계열 합격자", nur_df)
    section("교대 합격자", tch_df)


# ==================================================================
# 만든이
# ==================================================================
st.markdown(
    """
    <div style="position: fixed; bottom: 10px; left: 10px; font-size: 0.85rem;
                color: #64748b; background: rgba(255,255,255,0.85);
                padding: 5px 10px; border-radius: 8px; border: 1px solid #dbeafe;">
        만든이 · 함창고 교사 박호종
    </div>
    """,
    unsafe_allow_html=True,
)
