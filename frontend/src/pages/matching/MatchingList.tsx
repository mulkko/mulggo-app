import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/matchingList.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";

/**
 * 지원사업 매칭 리스트(공고 리스트) 화면.
 *
 * 자격이 맞는 정부지원사업을 카드 리스트로 보여준다. 상단에 지역/업종/정렬
 * 필터바가 있고, 하단에는 공통 BottomNav("매칭" 탭 활성).
 *
 * 목록은 GET /api/matching(필터 없음, 전체 목록)에서 가져온다. 지역/업종
 * 드롭다운, "필터" 팝업의 실제 필터링 반영은 아직 TODO.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const PAGE_SIZE = 20;

type MatchingListResponse = {
  success: boolean;
  data?: AnnouncementCardData[];
  has_more?: boolean;
  total?: number;
};

function MatchingList() {
  const navigate = useNavigate();
  const [announcements, setAnnouncements] = useState<AnnouncementCardData[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const fetchPage = (offset: number, onDone: (body: MatchingListResponse) => void) =>
    fetch(`${API_BASE_URL}/api/matching?offset=${offset}&limit=${PAGE_SIZE}`)
      .then((res) => res.json())
      .then((body: MatchingListResponse) => {
        if (body.success && body.data) {
          onDone(body);
        } else {
          setError("공고 목록을 불러오지 못했습니다.");
        }
      })
      .catch(() => setError("서버에 연결할 수 없습니다."));

  useEffect(() => {
    fetchPage(0, (body) => {
      setAnnouncements(body.data ?? []);
      setHasMore(body.has_more ?? false);
      setTotal(body.total ?? 0);
    }).finally(() => setLoading(false));
  }, []);

  const handleLoadMore = () => {
    setLoadingMore(true);
    fetchPage(announcements.length, (body) => {
      setAnnouncements((prev) => [...prev, ...(body.data ?? [])]);
      setHasMore(body.has_more ?? false);
    }).finally(() => setLoadingMore(false));
  };

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
    navigate("/matching/filter");
  };

  const handleCardClick = (item: AnnouncementCardData) => {
    // 공고 상세 화면으로 이동. id를 넘기면 상세 화면이 matchingDetailData에서
    // 해당 id의 더미데이터를 찾아 렌더한다.
    navigate(`/matching/${item.id}`);
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
          <span className={styles.countValue}>{total}건</span>
        </div>

        {loading && <p className={styles.guide}>불러오는 중...</p>}
        {error && <p className={styles.guide}>{error}</p>}

        <ul className={styles.cardList}>
          {announcements.map((item) => (
            <li key={item.id}>
              <AnnouncementCard item={item} onClick={handleCardClick} />
            </li>
          ))}
        </ul>

        {hasMore && (
          <button
            type="button"
            className={styles.loadMoreButton}
            onClick={handleLoadMore}
            disabled={loadingMore}
          >
            {loadingMore ? "불러오는 중..." : "더보기"}
          </button>
        )}
      </div>

      <BottomNav active="matching" />
    </div>
  );
}

export default MatchingList;
