"""
patent_forecast.py 의 키워드 생성 로직 검증용 테스트.
실제 LLM/KIPRIS 호출 없이(mock) 도메인 누락 감지 + 1회 재시도 + 안전 폴백만 확인한다.

사용법:  python backend/analysis_report/tech_startup/test_patent_forecast.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from backend.analysis_report.tech_startup import patent_forecast as pf


SEED = "농업"
PROBLEM = "방울토마토 재배 시 온습도 관리가 어려움"
SOLUTION = "스마트팜 자동 제어시스템"


# ----------------------------------------------------------------------
# 1. 도메인 누락 감지 휴리스틱 자체 검증
# ----------------------------------------------------------------------
assert pf._looks_domain_free("온습도 관리", SEED, SOLUTION) is True, "FAIL: 도메인 누락을 못 잡음"
assert pf._looks_domain_free("스마트팜 온습도", SEED, SOLUTION) is False, "FAIL: 정상 키워드를 잘못 걸러냄"
print("[PASS] 1. 도메인 누락 감지 (실패사례 잡고 정상사례 통과)")


# ----------------------------------------------------------------------
# 2. 1차 응답이 정상이면 재시도 없이 그대로 반환
# ----------------------------------------------------------------------
calls = []
pf._call_keyword_llm = lambda s, u: (calls.append(u) or '{"keyword": "스마트팜 온습도"}')

d = pf.generate_patent_keyword_with_debug(SEED, PROBLEM, SOLUTION)
assert d["keyword"] == "스마트팜 온습도", d
assert d["retried"] is False, d
assert len(calls) == 1, f"FAIL: 재시도 불필요한데 {len(calls)}번 호출됨"
print("[PASS] 2. 1차 응답 정상 → 재시도 없이 반환 (비용 절감)")


# ----------------------------------------------------------------------
# 3. 1차에 도메인 없으면 자동 재시도 → 2차 응답 반영 + debug 기록
# ----------------------------------------------------------------------
log = []


def _bad_then_good(system_prompt, user_prompt):
    log.append(user_prompt)
    if len(log) == 1:
        return '{"keyword": "온습도 관리"}'  # 실제 있었던 실패 그대로 재현
    return '{"keyword": "스마트팜 온습도"}'


pf._call_keyword_llm = _bad_then_good

d = pf.generate_patent_keyword_with_debug(SEED, PROBLEM, SOLUTION)
assert d["keyword"] == "스마트팜 온습도", f"FAIL: 재시도 결과 반영 안됨 {d}"
assert d["retried"] is True, d
assert len(log) == 2, f"FAIL: 재시도가 정확히 1번 더 일어나야 하는데 {len(log)}번"
assert "도메인 단어가 빠져 있다" in d["retry_prompt"], "FAIL: 재시도 프롬프트에 보정 지시 없음"
assert d["retry_raw_response"] == '{"keyword": "스마트팜 온습도"}', d
print("[PASS] 3. 도메인 누락 → 1회 재시도 → 보정된 결과로 교체 + debug 기록")


# ----------------------------------------------------------------------
# 4. 재시도해도 계속 실패하면 무한루프 없이 딱 1번만 재시도하고 종료
# ----------------------------------------------------------------------
count = {"n": 0}
pf._call_keyword_llm = lambda s, u: (count.__setitem__("n", count["n"] + 1) or '{"keyword": "온습도 관리"}')

d = pf.generate_patent_keyword_with_debug(SEED, PROBLEM, SOLUTION)
assert count["n"] == 2, f"FAIL: 최초+재시도 1회 총 2번이어야 하는데 {count['n']}번"
assert d["retried"] is True, d
print("[PASS] 4. 계속 실패 → 무한루프 없이 총 2번만 호출하고 종료")


# ----------------------------------------------------------------------
# 5. 파싱 실패 시 빈 문자열로 안전 폴백 (기존엔 KeyError로 500)
# ----------------------------------------------------------------------
pf._call_keyword_llm = lambda s, u: "이상한 응답"
kw = pf.generate_patent_keyword(SEED, "문제", SOLUTION)
assert kw == "", f"FAIL: 파싱 실패 시 빈 문자열이어야 하는데 {kw!r}"
print("[PASS] 5. 파싱 실패 → 빈 문자열 안전 폴백")


# ----------------------------------------------------------------------
# 6. get_patent_trend_with_forecast 의 keyword_debug 구조 유지
#    (KIPRIS 호출은 스텁으로 대체)
# ----------------------------------------------------------------------
pf._call_keyword_llm = lambda s, u: '{"keyword": "스마트팜 온습도"}'
pf.get_patent_count = lambda keyword, year, field="astrtCont": 100 + year

res = pf.get_patent_trend_with_forecast(SEED, PROBLEM, SOLUTION, past_years=list(range(2015, 2025)))
kd = res["keyword_debug"]
assert set(kd) == {"prompt", "raw_response", "retried", "retry_prompt", "retry_raw_response"}, set(kd)
assert res["keyword"] == "스마트팜 온습도", res["keyword"]
print("[PASS] 6. 파이프라인 keyword_debug 구조 유지 (prompt/raw_response + retry 정보)")


print("\n모든 테스트 통과 (6/6)")
