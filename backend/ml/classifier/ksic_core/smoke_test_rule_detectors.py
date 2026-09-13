"""rule_detectors.py 핵심 회귀 스모크 테스트.

프로젝트 루트에서 권장 실행:
    python -m ksic_core.smoke_test_rule_detectors
"""

from ksic_core.rule_detectors import (
    classify_occurrence_role,
    detect_explicit_scope,
    extract_explicit_ksic_details,
)

VALID = {
    "10", "34",
    "58222", "56211", "42201", "42202", "42203", "42204", "1042", "20111"
}


def roles(text):
    return [(x["code"], x["role"]) for x in extract_explicit_ksic_details(text, VALID)]


def run():
    # 1) 직접명시 코드 1개도 탐지해야 한다.
    assert ("58222", "positive") in roles("지원 업종코드: 58222")

    # 2) 제외코드는 positive가 아니어야 한다.
    assert ("56211", "excluded") in roles("지원 제외 업종\n업종코드 56211")

    # 3) 같은 코드가 positive/제외에 각각 등장하면 두 occurrence를 모두 보존한다.
    r = roles("지원 업종코드 56211\n\n지원 제외 업종\n업종코드 56211")
    assert ("56211", "positive") in r and ("56211", "excluded") in r

    # 4) '중' 부분제외는 코드 전체 제외/positive로 바꾸지 않는다.
    assert ("56211", "partial_exclusion") in roles("지원 제외 업종\n업종코드 56211 중 일부")

    # 5) 제외표의 예외는 전체 사업의 positive 업종으로 승격하지 않는다.
    assert ("56211", "exclusion_exception") in roles(
        "지원 제외 업종\n업종코드 56211 단, 사회적기업은 지원 가능"
    )

    # 6) 범위표기는 실제 마스터 코드 범위만 확장한다.
    rr = set(roles("지원 업종코드 42201~42204"))
    for c in ["42201", "42202", "42203", "42204"]:
        assert (c, "positive") in rr

    # 7) KSIC 헤더에서 멀리 떨어진 외딴 지번은 버린다.
    assert roles("한국표준산업분류 업종코드 안내\n" + "x" * 500 + "\n필지 1042") == []

    # 8) 소상공인/소기업 확인용 참고표의 C10~C34를 지원업종으로 올리면 안 된다.
    ref = (
        "지원대상: 음식점 소상공인\n"
        "참고2 소상공인 확인 기준\n"
        "소기업 규모 기준 및 소공인 규모 기준\n"
        "한국표준산업분류에 따른 제조업 중분류(C10~C34)"
    )
    rr = roles(ref)
    assert ("10", "positive") not in rr and ("34", "positive") not in rr

    # 9) '중소관광업체' 안의 '광업'은 광업 업종명이 아니다.
    s = "지원 대상: 담보력이 취약한 중소관광업체"
    i = s.find("광업")
    role, _ = classify_occurrence_role(
        s, i, i + len("광업"), candidate_text="광업", candidate_kind="name"
    )
    assert role == "non_target"

    # 10) 관광업 지원 목록에 '관광객이용시설업'이 같이 있다고 해서
    # 같은 줄의 '카지노업'을 비신청기업 이용시설 문맥으로 버리면 안 된다.
    s = (
        "신청자격: 사업자등록증 업종이 관광진흥법 제3조에 해당하는 자\n"
        "여행업, 관광숙박업, 관광객이용시설업, 국제회의업, 카지노업, 유원시설업"
    )
    i = s.find("카지노업")
    role, _ = classify_occurrence_role(
        s, i, i + len("카지노업"), candidate_text="카지노업", candidate_kind="name"
    )
    assert role == "positive"

    # 11) 지원대상이 '소상공인'인데 업종별 상시근로자 규모기준(제조업/건설업 등
    # 단어 나열)을 안내하는 것 뿐이면, 그 업종 단어 때문에 업종무관 판정이
    # 막히면 안 된다 (dev_gold_164 PBLN_000000000117022 실제 사례 축약형).
    scale_text = (
        "지원대상 : '자영업자 고용보험'에 가입한 소상공인(사업주)\n"
        "상시근로자 수 : 5명 미만 (단, 광업·제조업·건설업 및 운수업은 10명 미만)\n"
        "연간매출액 : 도소매업 50억원 이하, 제조업 120억원 이하"
    )
    scope = detect_explicit_scope(scale_text)
    assert scope and scope["status"] == "업종무관", scope

    # 12) 반대로 진짜 업종 제한이면 여전히 업종무관으로 오판하면 안 된다.
    real_limit_text = (
        "지원대상 : 관광진흥법상 관광숙박업을 영위하는 중소기업"
    )
    scope2 = detect_explicit_scope(real_limit_text)
    assert not (scope2 and scope2["status"] == "업종무관" and scope2["confidence"] == "MED"), scope2

    # 13) '지원 분야'(기술지원/마케팅 등 지원 프로그램 종류)는 업종 제한이
    # 아니다 (dev_gold_164 PBLN_000000000123769 실제 사례 축약형).
    program_field_text = (
        "지원대상: 본사 또는 공장이 인천 소재 중소기업(아래 요건 중 1개 이상 해당)\n"
        "① 중동 지역 수출실적이 있는 기업\n"
        "지원 분야 및 프로그램(최대 3개 선택)\n"
        "기술지원, 해외 마케팅, 수출 물류비"
    )
    scope3 = detect_explicit_scope(program_field_text)
    assert scope3 and scope3["status"] == "업종무관", scope3

    # 14) (G3) 신청자격의 '공장등록 필수'는 제조업(C)으로 본다.
    from ksic_core.rule_detectors import detect_manufacturing_requirement
    mfg = detect_manufacturing_requirement(
        "4. 지원대상\n융자신청일 현재 공장등록을 하고 가동 중인 중소기업"
    )
    assert mfg and mfg["확정코드"] == ["C"] and mfg["ksic_confidence"] == "MED", mfg

    # 15) (G3) '본사 또는 공장', '제출서류의 공장등록증 사본'은 발동하지 않는다.
    assert detect_manufacturing_requirement(
        "지원대상: 본사 또는 공장을 등록한 중소기업"
    ) is None
    assert detect_manufacturing_requirement(
        "제출서류: 사업자등록증 및 공장등록증 사본 각 1부"
    ) is None
    assert detect_manufacturing_requirement(
        "지원대상: 중소기업 (공장등록증 보유업체 제외)"
    ) is None

    # 16) (G4) 구(10차) KSIC 코드는 11차 코드로 변환해서 인식한다.
    from ksic_core.rule_detectors import _normalize_explicit_code, _load_legacy_map
    lm = _load_legacy_map()
    if lm:  # 크로스워크 파일이 있을 때만
        vc = {"56191", "10601", "71392"}  # 11차 유효코드(테스트용 축약)
        assert _normalize_explicit_code("56194", vc) == "56191"   # 김밥집: 10차→11차
        assert _normalize_explicit_code("10711", vc) == "10601"   # 떡류: 10차→11차
        assert _normalize_explicit_code("21210", vc) is None      # 1:N은 자동변환 안 함

    # 17) (G5) LLM 후보선택 프롬프트에 해설서 정의/제외가 주입되는지.
    try:
        import ksic_core.llm_match as _lm
        h = _lm._load_haeseol()
        if h:
            line = _lm._candidate_line(0, "21100", "기초 의약 물질 제조업")
            assert "기초 의약 물질 제조업" in line
            assert len(line) > len("1. 기초 의약 물질 제조업")  # 정의/제외가 붙었다
    except ImportError:
        pass  # llm 모듈 없는 배포환경

    print("OK - rule detector smoke tests passed")


if __name__ == "__main__":
    run()
