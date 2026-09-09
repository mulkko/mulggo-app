import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
    key: "bizAge",
    title: "사업신청가능업력",
    mode: "single",
    options: ["예비창업자", "1년미만", "2년미만", "3년미만", "5년미만", "7년미만", "10년미만"],
  },
  {
    key: "age",
    title: "사업대상연령",
    mode: "single",
    options: ["전체", "만 20세 미만", "만 20~39세", "만 40세 이상"],
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

/** 복수선택 그룹 토글 — 프로토타입 원본 로직. */
function toggleMulti(current: number[], index: number): number[] {
  if (index === 0) return [0];
  const withoutAll = current.filter((i) => i !== 0);
  const next = withoutAll.includes(index)
    ? withoutAll.filter((i) => i !== index)
    : [...withoutAll, index];
  return next.length === 0 ? [0] : next;
}

function FilterPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<FilterState>(INITIAL_STATE);

  const handleBack = () => {
    navigate("/matching");
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
    // TODO: 선택한 필터(filters)를 매칭 리스트 쿼리 파라미터/상태로 넘겨 실제 필터링에 반영
    navigate("/matching");
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
                    {option}
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
