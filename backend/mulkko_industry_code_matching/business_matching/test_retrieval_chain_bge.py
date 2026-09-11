"""
LLM 없이 검색→후보→상태 전 사슬을 실제 bge-m3 인덱스로 스모크.
(extract_activities 만 손으로 대체 — 나머지 build_queries / vector_search / build_candidate_pool /
 compute_confidence / decide_result_state 는 실코드 그대로.)  크레딧 0.

실행: python business_matching/test_retrieval_chain_bge.py
전제: 34_reindex_local.py --model bge-m3 가 끝나 있어야 함.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SD = Path(__file__).resolve().parent
sys.path.insert(0, str(SD))
_spec = importlib.util.spec_from_file_location("m23", SD / "23_match_business_code_v3.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["m23"] = m
_spec.loader.exec_module(m)

EMB = "bge-m3"

CASES = [
    dict(label="직접 로스팅 + 매장 판매 카페 (오프라인)", is_offline=True,
         act=dict(activity_name="매장 커피 판매", canonical_activity="커피 전문점",
                  business_role="음식·주점", priority="primary",
                  product_service="매장에서 만든 커피 음료", evidence="바리스타가 현장 제조",
                  search_keywords=["커피", "카페", "에스프레소"])),
    dict(label="반려동물 예방접종 알림 앱 (온라인)", is_offline=False,
         act=dict(activity_name="반려동물 건강관리 앱", canonical_activity="응용 소프트웨어 개발 및 공급업",
                  business_role="정보서비스·SW개발", priority="primary",
                  product_service="예방접종 알림·건강기록 관리 앱 구독",
                  evidence="앱을 개발해 구독료를 받음",
                  search_keywords=["소프트웨어", "앱", "구독", "건강관리"])),
    dict(label="스마트팜 장비 제조 (온라인)", is_offline=False,
         act=dict(activity_name="시설재배 장비 제조", canonical_activity="농업용 기계 제조업",
                  business_role="제조·가공", priority="primary",
                  product_service="스마트팜용 자동관수·환경제어 장비",
                  evidence="장비를 직접 설계·생산해 농가에 판매",
                  search_keywords=["농업용 기계", "관수 장비", "환경제어"])),
    dict(label="사입 의류 인터넷 쇼핑몰 (온라인)", is_offline=False,
         act=dict(activity_name="온라인 의류 소매", canonical_activity="전자상거래 소매업",
                  business_role="소매", priority="primary",
                  product_service="타 브랜드 의류를 사입해 자사몰 판매",
                  evidence="재고 매입 후 온라인 판매",
                  search_keywords=["전자상거래", "의류", "온라인 쇼핑몰"])),
]

ref_df = m.load_reference()
lookup = m.reference_lookup(ref_df)
col = m.open_chroma(EMB)
name_of = {c: v["business_name"] for c, v in lookup.items()}

for cs in CASES:
    act = cs["act"]
    queries = m.build_queries(act)
    vec = m.vector_search_multi(None, col, EMB, queries)
    kw = m.keyword_search(ref_df, act)
    pool = m.build_candidate_pool(vec, kw, lookup, act, cs["is_offline"])
    top = pool[0]
    act["classifiable"] = True
    conf = m.compute_confidence("mid", top, vec)
    raw1 = m.raw_text_top1(col, EMB, f"{cs['label']}")
    state = m.decide_result_state(act, pool, conf["confidence"], top["business_code"], raw1)

    print("=" * 78)
    print(f"{cs['label']}   (offline={cs['is_offline']})")
    print(f"  검색 1위 : {top['business_name']} ({top['business_code']})  cos={top.get('cosine_similarity')}")
    print(f"  후보 TOP5: " + " | ".join(f"{c['business_name']}({c['business_code']})" for c in pool[:5]))
    print(f"  신뢰도   : {conf['confidence']}  ({conf['confidence_downgrade_reason'] or '하향 없음'})")
    print(f"  결과 상태: {state['result_state']}  — {state['state_reason'] or 'OK'}")
    if state["clarifying_question"]:
        print(f"  확인 질문: {state['clarifying_question']}")
    assert pool, "pool 비어있음"
    assert state["result_state"] in m.RESULT_STATES

print("\n스모크 통과 — 검색→후보→상태 사슬 정상 (LLM 제외)")
