"""
사업자등록증 이미지 품질 게이트.

업로드 직후, 비싼 OCR 파이프라인을 돌리기 전에 EasyOCR(빠름)로 빠르게 훑어
문서가 인식 가능한 품질인지 판정한다. 실패 시 프론트에서 "재업로드 안내"를 띄운다.

판정 기준:
  - 사업자등록증 문서가 맞는지 (핵심 앵커 텍스트 존재)
  - 사업자등록번호(000-00-00000) 패턴 검출 여부
  - 핵심 항목 라인의 평균 인식 신뢰도

반환: {"acceptable": bool, "reason": str, "score": float, "hint": str}
"""

import re

from backend.assistant.category_ocr import _prep, get_reader

_BIZNO_RE = re.compile(r"\d{3}\s*-\s*\d{2}\s*-\s*\d{5}")
_ANCHORS = ("사업자등록증", "등록번호", "사업의종류", "대표자", "성명", "개업", "소재지", "법인명")

_HINT = "이미지가 흐리거나 잘려 인식이 어렵습니다. 밝은 곳에서 문서 전체가 나오도록 정면으로 다시 촬영해 업로드해주세요."


def check_image_quality(path_or_im, min_score=0.55):
    import numpy as np

    im = _prep(path_or_im)
    res = get_reader().readtext(np.array(im), detail=1, paragraph=False)
    if not res:
        return {"acceptable": False, "reason": "글자를 전혀 인식하지 못함", "score": 0.0, "hint": _HINT}

    texts = [(t, c) for _, t, c in res]
    joined = "".join(re.sub(r"\s+", "", t) for t, _ in texts)

    # 1. 사업자등록증 문서인지
    anchor_hits = sum(1 for a in _ANCHORS if a in joined)
    is_bizcert = ("사업자등록" in joined) or ("사업자등록증" in joined) or anchor_hits >= 3

    # 2. 사업자등록번호 패턴
    has_bizno = bool(_BIZNO_RE.search(" ".join(t for t, _ in texts)))

    # 3. 신뢰도 (한글 2글자 이상 박스만)
    hangul_confs = [c for t, c in texts if len(re.sub(r"[^가-힣]", "", t)) >= 2]
    avg_conf = sum(hangul_confs) / len(hangul_confs) if hangul_confs else 0.0

    # 종합 점수
    score = 0.0
    score += 0.35 if is_bizcert else 0.0
    score += 0.30 if has_bizno else 0.0
    score += 0.35 * min(avg_conf / 0.8, 1.0)

    if not is_bizcert:
        return {"acceptable": False, "reason": "사업자등록증으로 보이지 않음", "score": round(score, 2),
                "hint": "사업자등록증 이미지를 업로드해주세요. (다른 서류가 업로드된 것 같습니다)"}
    if score < min_score:
        return {"acceptable": False,
                "reason": f"인식 품질 낮음 (등록번호검출={has_bizno}, 평균신뢰도={avg_conf:.2f})",
                "score": round(score, 2), "hint": _HINT}
    return {"acceptable": True, "reason": "정상", "score": round(score, 2), "hint": ""}


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        r = check_image_quality(p)
        mark = "OK " if r["acceptable"] else "REJECT"
        print(f"[{mark}] score={r['score']}  {p.split(chr(92))[-1]}")
        print(f"        {r['reason']}")
