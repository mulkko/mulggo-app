import styles from "../../styles/matchingList.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";

/**
 * 지원사업 매칭 리스트(공고 리스트) 화면.
 *
 * 자격이 맞는 정부지원사업을 카드 리스트로 보여준다. 상단에 지역/업종/정렬
 * 필터바가 있고, 하단에는 공통 BottomNav("매칭" 탭 활성).
 *
 * 지금은 화면(레이아웃 + 더미데이터)만 만든다. 필터 동작, 카드 → 상세 이동,
 * 하단 탭 이동 등 실제 로직은 전부 TODO 주석으로만 표시.
 */

interface AnnouncementCard {
  id: string;
  /** 주관 기관명 */
  agency: string;
  /** 마감 임박도 뱃지 문구 (예: "모집중 D-6") */
  dday: string;
  /** 공고 제목 */
  title: string;
  /** 해시태그 2개 */
  tags: [string, string];
}

/**
 * 더미데이터.
 * 백엔드 매칭 API(자격/우대조건 순 정렬 결과)가 연결되면 이 배열을 응답 데이터로 교체한다.
 * 구조: id / agency(기관명) / dday(D-day 뱃지) / title(공고 제목) / tags(해시태그 2개).
 * 값 출처: 프로토타입 "공고 매칭 리스트" 화면의 예시 카드 5개.
 */
const DUMMY_ANNOUNCEMENTS: AnnouncementCard[] = [
  {
    id: "a1",
    agency: "중소벤처기업부",
    dday: "모집중 D-6",
    title: "2026년 청년 소상공인 창업 자금 지원",
    tags: ["#청년창업", "#소상공인"],
  },
  {
    id: "a2",
    agency: "여성기업종합지원센터",
    dday: "모집중 D-3",
    title: "여성 창업 아이디어 경진대회",
    tags: ["#여성창업", "#경진대회"],
  },
  {
    id: "a3",
    agency: "마포구청",
    dday: "모집중 D-18",
    title: "마포구 골목상권 특화 창업 지원사업",
    tags: ["#골목상권", "#지역특화"],
  },
  {
    id: "a4",
    agency: "소상공인시장진흥공단",
    dday: "모집중 D-32",
    title: "외식업 스마트 매장 전환 지원",
    tags: ["#외식업", "#스마트매장"],
  },
  {
    id: "a5",
    agency: "중소벤처기업부",
    dday: "모집중 D-45",
    title: "2026년 전 업종 소상공인 디지털 전환 지원",
    tags: ["#디지털전환", "#전업종"],
  },
];

function MatchingList() {
  const handleAnalysisClick = () => {
    // TODO: "물꼬 분석"(분석 리포트) 화면으로 이동
  };

  const handleRegionClick = () => {
    // TODO: 지역 선택 바텀시트/팝업 열기
  };

  const handleIndustryClick = () => {
    // TODO: 업종 드롭다운 열기
  };

  const handleSortClick = () => {
    // TODO: 정렬 드롭다운 열기 (최근 등록순 / 마감임박순 / 우대조건순 등)
  };

  const handleFilterClick = () => {
    // TODO: 상세 필터 패널(기업유형·업력 등)로 이동
  };

  const handleCardClick = (item: AnnouncementCard) => {
    // TODO: 공고 상세 화면으로 이동 (예: navigate(`/matching/${item.id}`))
    void item;
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 로고 + "물꼬 분석" 링크 */}
      <header className={styles.header}>
        <span className={styles.logo}>
          <span className={styles.logoText}>MULKKO MATCHING</span>
          <svg
            className={styles.logoMark}
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--color-light-teal)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 3c3 3.6 6 6.9 6 10.5A6 6 0 0 1 6 13.5C6 9.9 9 6.6 12 3Z" />
          </svg>
        </span>
        <button type="button" className={styles.analysisLink} onClick={handleAnalysisClick}>
          물꼬 분석
        </button>
      </header>

      {/* 필터바: 시각적 형태만. 클릭 동작은 전부 TODO */}
      <div className={styles.filterBar}>
        <button type="button" className={styles.regionChip} onClick={handleRegionClick}>
          <svg
            className={styles.pinIcon}
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M12 2C7.6 2 4 5.6 4 10c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8Zm0 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
          </svg>
          마포구 기준
        </button>
        <button type="button" className={styles.dropdownChip} onClick={handleIndustryClick}>
          업종 전체 ▾
        </button>
        <button type="button" className={styles.dropdownChip} onClick={handleSortClick}>
          최근 등록순 ▾
        </button>
        <button
          type="button"
          className={styles.filterButton}
          onClick={handleFilterClick}
          aria-label="상세 필터"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M4 8h10" />
            <path d="M18 8h2" />
            <path d="M4 16h6" />
            <path d="M14 16h6" />
            <circle cx="16" cy="8" r="2" />
            <circle cx="12" cy="16" r="2" />
          </svg>
        </button>
      </div>

      {/* 스크롤 영역: 안내 문구 + 카운트 박스 + 카드 리스트 */}
      <div className={styles.scrollArea}>
        <p className={styles.guide}>
          필터를 누르면 기업유형·업력 등 필터를 더 설정할 수 있어요
        </p>

        <div className={styles.countBox}>
          <span className={styles.countLabel}>총 매칭 사업</span>
          <span className={styles.countValue}>{DUMMY_ANNOUNCEMENTS.length}건</span>
        </div>

        <ul className={styles.cardList}>
          {DUMMY_ANNOUNCEMENTS.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={styles.card}
                onClick={() => handleCardClick(item)}
              >
                <div className={styles.cardTop}>
                  <span className={styles.agency}>{item.agency}</span>
                  <span className={styles.ddayBadge}>{item.dday}</span>
                </div>
                <span className={styles.cardTitle}>{item.title}</span>
                <div className={styles.tagRow}>
                  {item.tags.map((tag) => (
                    <span key={tag} className={styles.tag}>
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <BottomNav active="matching" />
    </div>
  );
}

export default MatchingList;
