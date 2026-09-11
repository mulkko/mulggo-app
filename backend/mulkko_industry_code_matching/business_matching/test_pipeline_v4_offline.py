"""
⑥ 파이프라인 개편 — LLM/검색/크레딧 없이 순수 로직만 오프라인 검증.
개정 계획서: Q5(is_offline_store 이진), 3상태, 확인질문. (수익모델 슬롯은 실제 폼에 없어 제외)

실행:  python business_matching/test_pipeline_v4_offline.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_M = Path(__file__).resolve().parent / "23_match_business_code_v3.py"
_spec = importlib.util.spec_from_file_location("m23", _M)
m = importlib.util.module_from_spec(_spec)
sys.modules["m23"] = m
_spec.loader.exec_module(m)


def _activity(product="원두를 볶아 판매", **kw):
    a = {
        "activity_name": "커피 가공", "canonical_activity": "커피 가공업",
        "business_role": "제조·가공", "priority": "primary",
        "product_service": product, "evidence": "직접 로스팅",
        "search_keywords": ["원두", "로스팅"], "classifiable": True,
    }
    a.update(kw)
    return a


def _pool(*sections):
    out = []
    for i, large in enumerate(sections, start=1):
        out.append({"business_code": f"{100000+i}", "business_name": f"후보{i}",
                    "biz_large_names": large, "candidate_rank": i})
    return out


C1 = "100001"  # _pool 첫 후보 코드 (선택/검색1위 매칭용)


def check(name, cond):
    print(("  OK  " if cond else "  FAIL") + "  " + name)
    assert cond, name


ok_seed = "직접 볶은 원두로 손님에게 커피를 만들어 파는 카페를 운영한다"
ok_prob = "동네에 스페셜티 커피를 마실 곳이 마땅치 않다"
ok_sol = "매장에서 바리스타가 에스프레소 음료를 제조해 현장에서 판매하고 원두도 소매한다"

# ---------------------------------------------------------------- validate_inputs
m.validate_inputs(ok_seed, ok_prob, ok_sol, True)
check("정상 입력 통과", True)
m.validate_inputs("커피에 관심 많음", ok_prob, ok_sol)   # 폼 예시처럼 짧은 Q1
check("짧은 Q1(폼 예시) 통과", True)

try:
    m.validate_inputs("짧", ok_prob, ok_sol); check("너무 짧은 seed 거부", False)
except ValueError:
    check("너무 짧은 seed 거부", True)

try:
    m.validate_inputs(ok_seed, ok_prob, ok_sol, is_offline_store="예"); check("is_offline_store 문자열 거부", False)
except ValueError:
    check("is_offline_store 문자열 거부", True)

# ---------------------------------------------------------------- _parse_offline
check("_parse_offline 예->True", m._parse_offline("예") is True)
check("_parse_offline 아니오->False", m._parse_offline("아니오") is False)
check("_parse_offline 공백->None", m._parse_offline("") is None)

# ---------------------------------------------------------------- store_conflict (Q5)
check("오프라인+제조업 -> 상충", m.store_conflict(True, "제조업") is True)
check("오프라인+농림어업 -> 상충", m.store_conflict(True, "농업, 임업 및 어업") is True)
check("오프라인+음식점 -> 상충아님", m.store_conflict(True, "숙박 및 음식점업") is False)
check("온라인 -> 항상 상충아님", m.store_conflict(False, "제조업") is False)
check("미입력 -> 상충아님", m.store_conflict(None, "제조업") is False)

# ---------------------------------------------------------------- _section_group
check("_section_group 제조업", m._section_group("제조업") == "제조")
check("_section_group 도매 및 소매", m._section_group("도매 및 소매업") == "도소매")
check("_section_group 정보통신", m._section_group("정보통신업") == "중개·SW·정보")
check("_section_group 금융 -> None", m._section_group("금융 및 보험업") is None)

# ---------------------------------------------------------------- decide_result_state (앙상블 게이트)
s = m.decide_result_state(_activity(), [], "high", C1, C1)
check("빈 pool -> 정보_추가_필요", s["result_state"] == "정보_추가_필요")

s = m.decide_result_state(_activity(classifiable=False), _pool("제조업"), "high", C1, C1)
check("classifiable=no -> 정보_추가_필요", s["result_state"] == "정보_추가_필요")

s = m.decide_result_state(_activity(product=""), _pool("제조업"), "high", C1, C1)
check("product 비었음 -> 정보_추가_필요", s["result_state"] == "정보_추가_필요")

s = m.decide_result_state(_activity(), _pool("제조업", "도매 및 소매업", "정보통신업"), "high", C1, C1)
check("역할 경계(3계열) -> 확인필요/역할질문",
      s["result_state"] == "사용자_확인_필요" and s["clarifying_question"] == m._ROLE_QUESTION)

s = m.decide_result_state(_activity(), _pool("제조업", "제조업"), "high", C1, C1)
check("high + 검색1위==선택 -> 추천_가능", s["result_state"] == "추천_가능")

s = m.decide_result_state(_activity(), _pool("제조업", "제조업"), "high", C1, "999999")
check("high + 검색1위!=선택 -> 확인필요 (앙상블 불일치)", s["result_state"] == "사용자_확인_필요")

s = m.decide_result_state(_activity(), _pool("제조업", "제조업"), "mid", C1, C1)
check("mid + 일치 -> 추천_가능 (A안: high 조건 없음)", s["result_state"] == "추천_가능")

s = m.decide_result_state(_activity(), _pool("제조업", "제조업"), "low", C1, "999999")
check("low + 불일치 -> 확인필요/후보쌍질문",
      s["result_state"] == "사용자_확인_필요" and "중" in s["clarifying_question"])

# ---------------------------------------------------------------- build_candidate_pool + Q5
lookup = {
    "111111": {"business_name": "커피 전문점", "biz_large_names": "숙박 및 음식점업"},
    "222222": {"business_name": "커피 가공업", "biz_large_names": "제조업"},
}
vec = [
    {"business_code": "222222", "vector_rank": 1, "cosine_similarity": 0.50},
    {"business_code": "111111", "vector_rank": 2, "cosine_similarity": 0.48},
]
kw = [{"business_code": "111111", "keyword_score": 0.9},
      {"business_code": "222222", "keyword_score": 0.4}]

pool_no_store = m.build_candidate_pool(vec, kw, lookup, _activity(), None)
pool_offline = m.build_candidate_pool(vec, kw, lookup, _activity(business_role="음식·주점"), True)

check("Q5 미입력: vector 1위(가공업)이 상위 유지",
      pool_no_store[0]["business_code"] == "222222")
check("Q5 오프라인: 커피 전문점(111111)이 커피 가공업 위로",
      pool_offline[0]["business_code"] == "111111")
check("Q5 오프라인: 커피 가공업 role_fit=2(상충) 로 마킹됨",
      next(c for c in pool_offline if c["business_code"] == "222222")["role_fit"] == 2)

print("\n전부 통과 OK")
