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

    # 주요합격 앞에 붙은 숫자 + ; 또는 숫자 + , 패턴 찾기
    extracted = offer_text.str.extract(r'^\s*"?(\d+)\s*[;,]\s*"?(.+)$')

    mask = extracted[0].notna() & extracted[1].notna()

    # 고등학교석차가 비어 있거나 None인 경우에만 앞 숫자를 석차로 복구
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
