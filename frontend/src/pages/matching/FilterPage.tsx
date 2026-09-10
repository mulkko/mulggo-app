import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import styles from "../../styles/filterPage.module.css";

/**
 * 전체 필터 화면.
 *
 * 매칭 리스트(`/matching`)의 "전체 필터" 진입점에서 들어온다.
 * 4개 필터 그룹(기업유형 / 지원분야 / 사업신청가능업력 / 사업대상연령)을
 * 위에서 아래로 배치하고, 각 그룹은 제목 + note + 칩 목록으로 구성한다.
 *
 * 이 화면에는 하단 네비게이션(BottomNav)이 없다 — 상단에 뒤로가기 헤더만 있는 구조.
 * (헤더 패턴은 MatchingDetail.tsx 참고)
 *
 * 선택 로직은 프로토타입("is.filter") 원본 그대로:
 * - 복수선택 그룹(company/field): "전체"(index 0) 클릭 시 [0]으로 초기화.
 *   다른 항목 클릭 시 0을 제거한 뒤 토글(있으면 제거, 없으면 추가). 결과가 비면 다시 [0].
 * - 단일선택 그룹(bizAge/age): 클릭한 index로 값 교체.
 * - "초기화": company=[0], field=[0], bizAge=0, age=0.
 */

type GroupKey = "company" | "field" | "bizAge" | "age";

type FilterGroup = {
  key: GroupKey;
  title: string;
  mode: "multi" | "single";
  options: string[];
};

/** 필터 그룹 데이터 — 프로토타입 값 그대로 하드코딩. */
const FILTER_GROUPS: FilterGroup[] = [
  {
    // [2026-09-09] announcements.target_summary(bizinfo) 실제 distinct 값 기준으로 교체.
    // 기존엔 프로토타입 값 그대로라 "청소년/대학생/일반인" 등 실제 데이터에 없는 항목이
    // 섞여 있었고, 실제로 있는 "여성기업"은 빠져 있었음.
    key: "company",
    title: "기업유형 (지원대상)",
    mode: "multi",
    options: [
      "전체",
      "소상공인",
      "창업벤처",
      "중소기업",
      "사회적기업",
      "여성기업",
      "장애인기업",
      "마을기업",
      "협동조합",
      "제조업",
    ],
  },
  {
    key: "field",
    title: "지원분야",
    mode: "multi",
    options: [
      "전체",
      "내수",
      "경영",
      "사업화",
      "시설ㆍ공간ㆍ보육",
      "글로벌",
      "멘토링ㆍ컨설팅ㆍ교육",
      "창업교육",
      "행사ㆍ네트워크",
      "판로ㆍ해외진출",
      "기술개발(R&D)",
      "정책자금",
      "융자ㆍ보증",
      "인력",
      "수출",
      "기술",
      "창업",
      "금융",
      "기타",
    ],
  },
  {
    // [2026-09-09] announcements.business_age_condition(kstartup만 값 있음) 실제
    // distinct 값 기준으로 교체. "2년미만"은 실제 데이터에 없어서 제거, "업력무관" 추가.
    // "전체"(index 0)를 추가해서 단일선택이어도 "필터 없음" 상태를 가질 수 있게 함
    // (원래는 이게 없어서 항상 "예비창업자"가 기본 선택된 것처럼 취급됐음).
    key: "bizAge",
    title: "사업신청가능업력",
    mode: "single",
    options: ["전체", "예비창업자", "1년미만", "3년미만", "5년미만", "7년미만", "10년미만", "업력무관"],
  },
  {
    // [2026-09-10] announcements.target_age_groups(kstartup만 값 있음) 실제 distinct
    // 값 그대로 교체 - 가공된 버킷 없이 원본 10개 값 그대로 노출(docs/filter_options_
    // review_2026-09-09.xlsx "target_age_groups" 시트 참고).
    key: "age",
    title: "사업대상연령",
    mode: "single",
    options: [
      "전체",
      "만 15세 이상",
      "만 19세 이상",
      "만 19세~39세",
      "만 20세 이상",
      "만 20세 이상 ~ 만 39세 이하",
      "만 34세 이하",
      "만 39세 이하",
      "만 40세 이상",
      "만 45세 이하",
      "전연령",
    ],
  },
];

type FilterState = {
  company: number[];
  field: number[];
  bizAge: number;
  age: number;
};

const INITIAL_STATE: FilterState = {
  company: [0],
  field: [0],
  bizAge: 0,
  age: 0,
};

// [2026-09-10] "예비창업자"는 화면 표시만 "예비창업자 포함"으로 바꾸기로 결정(2축 분리는
// 안 함). 실제 값(DB LIKE 매칭에 쓰이는 값)은 그대로 "예비창업자" 유지 - 여기 라벨만 교체.
const CHIP_LABEL_OVERRIDES: Record<string, string> = {
  예비창업자: "예비창업자 포함",
};

/** 복수선택 그룹 토글 — 프로토타입 원본 로직. */
function toggleMulti(current: number[], index: number): number[] {
  if (index === 0) return [0];
  const withoutAll = current.filter((i) => i !== 0);
  const next = withoutAll.includes(index)
    ? withoutAll.filter((i) => i !== index)
    : [...withoutAll, index];
  return next.length === 0 ? [0] : next;
}

/** MatchingList가 handleFilterClick에서 넘겨준 현재 URL 쿼리로 칩 선택 상태를 복원한다.
 * 없거나 못 찾는 값은 INITIAL_STATE와 동일하게 "전체"로 둔다. */
function parseInitialState(searchParams: URLSearchParams): FilterState {
  const multiIndexes = (group: FilterGroup, param: string): number[] => {
    const labels = (searchParams.get(param) ?? "").split(",").map((s) => s.trim()).filter(Boolean);
    const indexes = labels.map((label) => group.options.indexOf(label)).filter((i) => i > 0);
    return indexes.length > 0 ? indexes : [0];
  };

  const singleIndex = (group: FilterGroup, param: string): number => {
    const label = searchParams.get(param) ?? "";
    const index = group.options.indexOf(label);
    return index > 0 ? index : 0;
  };

  return {
    company: multiIndexes(FILTER_GROUPS.find((g) => g.key === "company")!, "company"),
    field: multiIndexes(FILTER_GROUPS.find((g) => g.key === "field")!, "field"),
    bizAge: singleIndex(FILTER_GROUPS.find((g) => g.key === "bizAge")!, "biz_age"),
    age: singleIndex(FILTER_GROUPS.find((g) => g.key === "age")!, "age"),
  };
}

function FilterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<FilterState>(() => parseInitialState(searchParams));

  const handleBack = () => {
    // "적용하기" 없이 그냥 나가는 거라, 들어올 때 있던 필터를 그대로 유지한 채 돌아간다
    // (여기서 bare "/matching"으로 가면 이미 적용돼있던 필터가 사라짐).
    navigate(`/matching${searchParams.toString() ? `?${searchParams.toString()}` : ""}`);
  };

  const handleReset = () => {
    setFilters(INITIAL_STATE);
  };

  const handleChipClick = (group: FilterGroup, index: number) => {
    setFilters((prev) => {
      if (group.mode === "multi") {
        const key = group.key as "company" | "field";
        return { ...prev, [key]: toggleMulti(prev[key], index) };
      }
      const key = group.key as "bizAge" | "age";
      return { ...prev, [key]: index };
    });
  };

  const isSelected = (group: FilterGroup, index: number) => {
    if (group.mode === "multi") {
      const key = group.key as "company" | "field";
      return filters[key].includes(index);
    }
    const key = group.key as "bizAge" | "age";
    return filters[key] === index;
  };

  const handleApply = () => {
    // [2026-09-10] 4개 그룹 전부 실제 데이터 기준 값이라 그대로 넘긴다.
    const companyGroup = FILTER_GROUPS.find((g) => g.key === "company")!;
    const selectedCompanies = filters.company
      .filter((i) => i !== 0) // 0 = "전체" - 필터 없음
      .map((i) => companyGroup.options[i]);

    const fieldGroup = FILTER_GROUPS.find((g) => g.key === "field")!;
    const selectedFields = filters.field
      .filter((i) => i !== 0) // 0 = "전체" - 필터 없음
      .map((i) => fieldGroup.options[i]);

    const bizAgeGroup = FILTER_GROUPS.find((g) => g.key === "bizAge")!;
    const selectedBizAge = filters.bizAge !== 0 ? bizAgeGroup.options[filters.bizAge] : "";

    const ageGroup = FILTER_GROUPS.find((g) => g.key === "age")!;
    const selectedAge = filters.age !== 0 ? ageGroup.options[filters.age] : "";

    // 지역/업종/정렬(region/ksic/sort) 등 이 화면이 모르는 다른 쿼리 파라미터는
    // 그대로 유지하고, 여기서 다루는 4개 값만 새로 덮어쓴다.
    const params = new URLSearchParams(searchParams);
    params.delete("company");
    params.delete("field");
    params.delete("biz_age");
    params.delete("age");
    if (selectedCompanies.length > 0) {
      params.set("company", selectedCompanies.join(","));
    }
    if (selectedFields.length > 0) {
      params.set("field", selectedFields.join(","));
    }
    if (selectedBizAge) {
      params.set("biz_age", selectedBizAge);
    }
    if (selectedAge) {
      params.set("age", selectedAge);
    }
    navigate(`/matching${params.toString() ? `?${params.toString()}` : ""}`);
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 뒤로가기 + "필터" + 초기화 */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button
            type="button"
            className={styles.backButton}
            onClick={handleBack}
            aria-label="뒤로가기"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.headerTitle}>필터</span>
        </div>
        <button type="button" className={styles.resetButton} onClick={handleReset}>
          초기화
        </button>
      </header>

      <div className={styles.body}>
        {FILTER_GROUPS.map((group) => (
          <section key={group.key} className={styles.group}>
            <h2 className={styles.groupTitle}>
              {group.title}
              <span className={styles.groupNote}>
                {group.mode === "multi" ? "(복수선택)" : "(단일선택)"}
              </span>
            </h2>
            <div className={styles.chipList}>
              {group.options.map((option, index) => {
                const selected = isSelected(group, index);
                return (
                  <button
                    key={option}
                    type="button"
                    className={`${styles.chip} ${selected ? styles.chipOn : styles.chipOff}`}
                    aria-pressed={selected}
                    onClick={() => handleChipClick(group, index)}
                  >
                    {CHIP_LABEL_OVERRIDES[option] ?? option}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      {/* 하단 CTA: 적용하기 */}
      <div className={styles.cta}>
        <button type="button" className={styles.applyButton} onClick={handleApply}>
          적용하기
        </button>
      </div>
    </div>
  );
}

export default FilterPage;
