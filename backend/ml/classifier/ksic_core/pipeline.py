# ksic_core/pipeline.py
#
# [2026-09-03] 원문추출 -> 지역매핑 -> 업종매칭, 세 단계를 공고 1건 단위로
# 잇는 오케스트레이터. 지금까지는 3개 스크립트(extract_all_texts.py,
# region_apply_full.py, ksic_apply_full.py)를 각자 따로 돌리고, 결과 3개
# CSV를 공고ID로 사람이 다시 join해서 봐야 했다 — 이 파일은 그 세 단계를
# 함수 호출 체인으로 이어서 공고 1건당 결과 1행으로 바로 뽑는다.
#
# 세 로직을 다시 구현하지 않았다. 전부 이미 각자 검증된 순수함수를 그대로
# 가져다 쓴다:
#   - get_notice_full_text()  <- scripts2/extract_all_texts.py
#   - extract_region()        <- ksic_core/extract_region.py
#   - decide_industry()       <- ksic_core/decide_industry.py
#
# 세 단계는 비용이 완전히 다르다 — 이 차이를 그대로 설계에 반영한다:
#   - 원문추출: 네트워크 다운로드 + (필요시) OCR. 느리고 무겁다.
#     -> cached_text가 주어지면(=이미 추출된 적 있으면) 반드시 재사용하고
#        절대 다시 다운로드/OCR하지 않는다.
#   - 지역매핑: 순수 CPU 문자열 처리, 사실상 공짜. -> 매번 새로 계산.
#   - 업종매칭 1단계: 순수 CPU 문자열 대조, 사실상 공짜. -> 매번 새로 계산.
#   - 업종매칭 2단계(LLM): API 호출, 비용·시간 발생.
#     -> use_llm_fallback=False가 기본. 호출 여부는 호출자(driver 스크립트)가
#        명시적으로 결정하게 한다 — 이 함수 안에서 몰래 API를 부르지 않는다.
#
# 이 파일은 개별 단계 스크립트(region_apply_full.py, ksic_apply_full.py 등)를
# 대체하지 않는다. 오늘 KSIC 919건만 다시 판단했던 것처럼, 특정 단계만 따로
# 돌려야 할 일이 실제로 자주 있었다 — 그런 용도엔 여전히 개별 스크립트를 쓰고,
# 이 오케스트레이터는 "처음부터 끝까지 한 번에" 돌릴 때만 쓴다.

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
SCRIPTS2_DIR = os.path.join(ROOT, "scripts2")

for p in (ROOT, SCRIPTS_DIR, SCRIPTS2_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ksic_core.extract_region import extract_region, normalize_kstartup_region
from ksic_core.decide_industry import decide_industry, needs_human_review
from extract_all_texts import get_notice_full_text  # scripts2 — argparse는 main()에만 있어 import 안전
from region_apply_full import STATUS_DESC as REGION_STATUS_DESC  # scripts — 지역 status 설명 재사용

# 두 소스 다 이 키 집합으로 결과를 반환한다 — 소스가 뭐든 announcements
# 통합 스키마(ksic_codes/region_status 등)에 그대로 흘려넣을 수 있게.
RESULT_KEYS = [
    "공고ID", "공고명", "원문", "추출상태",
    "region_display", "region_list", "region_status", "region_method",
    "확정단계", "확정코드", "확정업종명", "ksic_confidence", "업종_확인필요",
]


def build_match_text(row, raw_text):
    """업종매칭용 텍스트 조합. ksic_apply_full.py의 build_match_text()와 동일 방식
    (공고명 | 해시태그 | 원문) — 검증된 조합을 그대로 재사용."""
    title = str(row.get("pblancNm", "") or "")
    hashtags = str(row.get("hashtags", "") or "")
    body = raw_text or ""
    return " | ".join(p for p in [title, hashtags, body] if p)


def process_bizinfo_notice(row, cached_text=None, cached_status=None, use_llm_fallback=False):
    """
    기업마당(bizinfo.csv) 공고 1건을 3단계에 순서대로 통과시켜 결과 1행을 만든다.

    cached_text/cached_status: 이미 추출된 원문이 있으면(빈 문자열이어도, 즉 추출
    실패였어도) 여기 넘겨서 원문추출 단계를 완전히 건너뛴다. 둘 다 None이면 이
    함수 안에서 직접 다운로드+추출을 시도한다(느릴 수 있음).

    use_llm_fallback: 업종매칭 2단계(LLM, 유료 API 호출) 사용 여부. 기본 False —
    켜고 싶으면 호출하는 쪽에서 명시적으로 True를 넘겨야 한다.

    반환: 원문추출 + 지역매핑 + 업종매칭 결과를 한 dict로 합친 것. 세 단계 중
    어느 것이 실패해도(원문 없음/지역 특정불가/업종 특정불가) 예외를 던지지
    않고 해당 필드만 빈 값/특정불가로 채운다 — 1,589건을 돌릴 때 한 건의
    실패가 전체를 멈추면 안 되기 때문(기존 세 스크립트도 전부 이 원칙).
    """
    notice_id = row.get("pblancId", "")

    if cached_text is not None:
        text, extract_status = cached_text, (cached_status or "cached")
    else:
        text, extract_status = get_notice_full_text(row.get("printFlpthNm", ""))
        text = text or ""

    region_result = extract_region(
        row.get("pblancNm", ""),
        row.get("jrsdInsttNm", ""),
        row.get("bsnsSumryCn", ""),
        full_text=text,
    )
    region_status = region_result.get("status", "")

    match_text = build_match_text(row, text)
    industry_result = decide_industry(match_text, use_llm_fallback=use_llm_fallback) if match_text.strip() else None

    return {
        "공고ID": notice_id,
        "공고명": row.get("pblancNm", ""),
        "원문": text,
        "추출상태": extract_status,
        "region_display": region_result.get("display", ""),
        "region_list": "|".join(region_result.get("regions") or []),
        "region_status": region_status,
        "region_method": REGION_STATUS_DESC.get(region_status, ""),
        "확정단계": industry_result["확정단계"] if industry_result else "특정불가",
        "확정코드": "|".join(industry_result["확정코드"]) if industry_result else "",
        "확정업종명": "|".join(industry_result["확정업종명"]) if industry_result else "",
        "ksic_confidence": industry_result.get("ksic_confidence", "") if industry_result else "",
        "업종_확인필요": "Y" if (industry_result and needs_human_review(industry_result)) else "N",
    }


# [2026-09-04 추가] 창업진흥원(K-Startup) 공고 1건 처리.
#
# 기업마당과 원본 컬럼명이 완전히 달라서 별도 함수로 뺐다 — 로직을 다시
# 만든 게 아니라 소스별로 다른 어댑터가 필요할 뿐이다(파이프라인 설계
# 문서에 이미 적어둔 원칙 그대로).
#
#   원문추출 : 첨부파일 다운로드 URL 필드 자체가 없어서 원천적으로 스킵.
#   지역매핑 : extract_region()의 텍스트 추론 대신 normalize_kstartup_region()
#              으로 supt_regin 구조화 필드를 직접 정규화(253건 실측 검증,
#              불일치 0건 — 텍스트 추론보다 오히려 더 신뢰도 높음).
#   업종매칭 : 아예 시도하지 않는다. 253건 재검증 결과 확정된 소수(13건)
#              조차 대부분 기관명 우연 충돌(국립공주대학교->축산업,
#              명지전문대학->전문대학 등)이라 신뢰 불가 판정 — 전부
#              "업종무관(기본값)"으로 고정(사용자 지시, 2026-09-04).
def process_kstartup_notice(row):
    """
    K-Startup(startup_sample_260826_마감공고제외.xlsx) 원본 행(dict, 영문 API
    필드명 키)을 받아 bizinfo와 동일한 키 집합(RESULT_KEYS)으로 반환한다.
    """
    notice_id = row.get("pbanc_sn", "") or row.get("id", "")

    region_result = normalize_kstartup_region(row.get("supt_regin", ""))
    region_status = region_result.get("status", "")

    return {
        "공고ID": notice_id,
        "공고명": row.get("biz_pbanc_nm", ""),
        "원문": "",
        "추출상태": "no_attachment_url_field",
        "region_display": region_result.get("display", ""),
        "region_list": "|".join(region_result.get("regions") or []),
        "region_status": region_status,
        "region_method": REGION_STATUS_DESC.get(region_status, ""),
        "확정단계": "업종무관(기본값)",
        "확정코드": "",
        "확정업종명": "",
        "ksic_confidence": "HIGH",
        "업종_확인필요": "N",
    }


# 소스 이름 -> 처리 함수. 새 소스 추가 시 여기 한 줄만 늘리면 됨.
_SOURCE_HANDLERS = {
    "bizinfo": process_bizinfo_notice,
    "kstartup": process_kstartup_notice,
}


def process_notice(row, source="bizinfo", **kwargs):
    """
    공고 1건을 소스에 맞는 처리 함수로 분기하는 통합 진입점.
    "매칭 기능을 파이썬 파일 하나로 통합"하려면 이 함수 하나만 호출하면
    되고, 소스별 컬럼명 차이는 이 함수 뒤로 전부 숨겨진다.

    source: "bizinfo"(기본값, 기존 호출부와 호환) | "kstartup"
    kwargs: bizinfo만 받는 옵션(cached_text/cached_status/use_llm_fallback)을
            그대로 전달 — kstartup은 해당 옵션이 없으므로 무시된다.
    """
    handler = _SOURCE_HANDLERS.get(source)
    if handler is None:
        raise ValueError(f"알 수 없는 source: {source!r} (지원: {list(_SOURCE_HANDLERS)})")

    if source == "bizinfo":
        return handler(row, **kwargs)
    return handler(row)
