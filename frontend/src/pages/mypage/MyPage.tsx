import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/myPage.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";

/**
 * 마이페이지 화면.
 *
 * 프로필 요약 + 나의 분석 리포트 / 관심있는 지원사업 / 채우기 이용내역 / 나의 지원내역
 * 4개 섹션 + 하단 공통 BottomNav("마이페이지" 탭 활성).
 *
 * 지금은 화면(레이아웃 + 더미데이터)만 만든다. 백엔드 연동 전이라
 * 각 카드의 삭제(X) 버튼만 "로컬 state에서 해당 항목 제거" 동작으로 실제 구현하고
 * (새로고침하면 더미데이터가 다시 채워짐), 나머지 화면 이동은 전부 TODO 주석으로만 표시.
 *
 * 삭제 state 구조: 삭제 가능한 섹션마다 별도의 useState 배열을 두고,
 * 삭제 시 `setX(prev => prev.filter(item => item.id !== id))` 로 해당 id만 걸러낸다.
 * 관심 지원사업 카드는 공고 리스트와 동일한 공통 컴포넌트 AnnouncementCard 를 재사용한다.
 */

interface AnalysisReport {
  id: string;
  /** 업종명 (예: "숙박 및 음식점업 (커피 전문점)") */
  industry: string;
  /** 업종코드 + 분석 요약 */
  summary: string;
  /** 생성일 문구 */
  createdAt: string;
}

interface FillHistoryItem {
  id: string;
  title: string;
  description: string;
  /** 뱃지 문구 (예: "다운로드 가능") */
  badge: string;
}

interface ApplyHistoryItem {
  id: string;
  title: string;
  /** 상태 뱃지 문구 (예: "지원함") */
  status: string;
  /** 지원일 (YYYY.MM.DD) */
  date: string;
}

/* ===== 더미데이터 (값 출처: 프로토타입 "마이페이지" 화면) =====
   백엔드 연동 시 각 배열을 API 응답으로 교체한다. */

const DUMMY_REPORTS: AnalysisReport[] = [
  {
    id: "r1",
    industry: "숙박 및 음식점업 (커피 전문점)",
    summary: "업종코드 552303 · 서교동 주변 상권 동향",
    createdAt: "2026.08.20 생성",
  },
  {
    id: "r2",
    industry: "전문, 과학 및 기술 서비스업 (전기ㆍ전자공학 연구개발업)",
    summary: "업종코드 730005 · 업종 및 특허 분석 지표",
    createdAt: "2026.08.12 생성",
  },
];

const DUMMY_INTERESTS: AnnouncementCardData[] = [
  {
    id: "i1",
    agency: "중소벤처기업부",
    dday: "모집중 D-6",
    title: "2026년 청년 소상공인 창업 자금 지원",
    tags: ["#청년창업", "#소상공인"],
  },
  {
    id: "i2",
    agency: "마포구청",
    dday: "모집중 D-18",
    title: "마포구 골목상권 특화 창업 지원사업",
    tags: ["#골목상권", "#지역특화"],
  },
];

const DUMMY_FILL_HISTORY: FillHistoryItem[] = [
  {
    id: "f1",
    title: "2026년 청년 소상공인 창업 자금 지원",
    description: "채우기 이용했던 서류들을 다시 다운로드 받을 수 있습니다.",
    badge: "다운로드 가능",
  },
];

const DUMMY_APPLY_HISTORY: ApplyHistoryItem[] = [
  {
    id: "p1",
    title: "마포구 골목상권 특화 창업 지원사업",
    status: "지원함",
    date: "2026.08.10",
  },
];

/** 카드 우측 상단 삭제(X) 버튼 (공통 스펙: 22x22 원형, hover 배경). */
function DeleteButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className={styles.deleteBtn}
      aria-label="목록에서 삭제"
      onClick={onClick}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </button>
  );
}

function MyPage() {
  const navigate = useNavigate();

  // 삭제 가능한 섹션마다 별도 로컬 state (백엔드 연동 전이라 새로고침 시 초기화됨)
  const [reports, setReports] = useState<AnalysisReport[]>(DUMMY_REPORTS);
  const [interests, setInterests] = useState<AnnouncementCardData[]>(DUMMY_INTERESTS);
  const [fillHistory, setFillHistory] = useState<FillHistoryItem[]>(DUMMY_FILL_HISTORY);
  const [applyHistory, setApplyHistory] = useState<ApplyHistoryItem[]>(DUMMY_APPLY_HISTORY);

  const removeById =
    <T extends { id: string }>(setter: React.Dispatch<React.SetStateAction<T[]>>) =>
    (id: string) =>
      setter((prev) => prev.filter((item) => item.id !== id));

  const handleContactClick = () => {
    // TODO: 고객센터 화면/채널로 이동
  };

  const handleProfileClick = () => {
    navigate("/mypage/edit");
  };

  const handleNewAnalysisClick = () => {
    // TODO: 새 분석(사업 구체화 챗봇) 시작 화면으로 이동
  };

  const handleReportClick = (_id: string) => {
    // TODO: 해당 분석 리포트 상세 화면으로 이동
  };

  const handleViewAllInterests = () => {
    navigate("/matching");
  };

  const handleInterestCardClick = (item: AnnouncementCardData) => {
    // TODO: 공고 상세 화면으로 이동 (navigate(`/matching/${item.id}`) — 관심목록 id 체계 확정 후 연결)
    void item;
  };

  const handleFillHistoryClick = (_id: string) => {
    // TODO: 채우기 이용내역 상세/서류 다운로드 화면으로 이동
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 1. 헤더: "MULKKO PAGE" 로고 + 우측 고객센터 아이콘 */}
      <header className={styles.header}>
        <span className={styles.logo}>
          <span className={styles.logoText}>MULKKO PAGE</span>
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
        <button
          type="button"
          className={styles.contactBtn}
          aria-label="고객센터"
          onClick={handleContactClick}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M4 13a8 8 0 0 1 16 0v3.5a2 2 0 0 1-2 2h-1v-6h3" />
            <path d="M4 13v3.5a2 2 0 0 0 2 2h1v-6H4" />
            <path d="M9 18.5h2a1.3 1.3 0 0 1 0 2.6H9" />
          </svg>
        </button>
      </header>

      <div className={styles.scrollArea}>
        {/* 2. 프로필 요약 카드 — 클릭 시 프로필 수정 화면(/mypage/edit)으로 이동 */}
        <button type="button" className={styles.profileCard} onClick={handleProfileClick}>
          <span className={styles.profileInfo}>
            <span className={styles.profileName}>김창업 님</span>
            <span className={styles.profileSub}>예비창업자 · 마포구</span>
          </span>
          <span className={styles.profileArrow} aria-hidden="true">
            ›
          </span>
        </button>

        {/* 3. 나의 분석 리포트 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>나의 분석 리포트</h2>
          {reports.map((report) => (
            <div key={report.id} className={styles.reportCard}>
              <button
                type="button"
                className={styles.reportBody}
                onClick={() => handleReportClick(report.id)}
              >
                <span className={styles.reportIndustry}>{report.industry}</span>
                <span className={styles.reportSummary}>{report.summary}</span>
                <span className={styles.reportDate}>{report.createdAt}</span>
              </button>
              <DeleteButton onClick={() => removeById(setReports)(report.id)} />
            </div>
          ))}
          <button
            type="button"
            className={styles.newAnalysisBtn}
            onClick={handleNewAnalysisClick}
          >
            + 새 분석 시작하기
          </button>
        </section>

        {/* 4. 관심있는 지원사업 — 공고 리스트 카드 컴포넌트(AnnouncementCard) 재사용 */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>관심있는 지원사업</h2>
            <button
              type="button"
              className={styles.viewAllBtn}
              onClick={handleViewAllInterests}
            >
              전체보기 →
            </button>
          </div>
          {interests.map((item) => (
            <AnnouncementCard
              key={item.id}
              item={item}
              onClick={handleInterestCardClick}
              onDelete={removeById(setInterests)}
            />
          ))}
        </section>

        {/* 5. 채우기 이용내역 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>채우기 이용내역</h2>
          {fillHistory.map((item) => (
            <div key={item.id} className={styles.fillCard}>
              <button
                type="button"
                className={styles.fillBody}
                onClick={() => handleFillHistoryClick(item.id)}
              >
                <span className={styles.fillTitle}>{item.title}</span>
                <span className={styles.fillDesc}>{item.description}</span>
                <span className={styles.fillBadge}>{item.badge}</span>
              </button>
              <DeleteButton onClick={() => removeById(setFillHistory)(item.id)} />
            </div>
          ))}
        </section>

        {/* 6. 나의 지원내역 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>나의 지원내역</h2>
          {applyHistory.map((item) => (
            <div key={item.id} className={styles.applyCard}>
              <span className={styles.applyTitle}>{item.title}</span>
              <span className={styles.applyMeta}>
                <span className={styles.applyStatus}>{item.status}</span>
                <span className={styles.applyDate}>{item.date}</span>
              </span>
              <DeleteButton onClick={() => removeById(setApplyHistory)(item.id)} />
            </div>
          ))}
        </section>
      </div>

      {/* 7. 하단 네비게이션 ("마이페이지" 탭 활성) */}
      <BottomNav active="my" />
    </div>
  );
}

export default MyPage;
