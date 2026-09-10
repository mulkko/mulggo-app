import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
 * 목록은 GET /api/matching에서 가져온다. 지역/업종 드롭다운, "필터" 팝업
 * (기업유형/지원분야/업력/연령) 전부 실제 필터링이 반영됨.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const PAGE_SIZE = 20;

type MatchingListResponse = {
  success: boolean;
  data?: AnnouncementCardData[];
  has_more?: boolean;
  total?: number;
};

// [2026-09-09, 테스트용] 업종 드롭다운 - 전체 KSIC(1,200여개) 대신, 실제 공고에서
// 자주 매칭된 것 중 몇 개만 넣어서 필터링 자체가 잘 되는지 확인하는 용도.
const KSIC_OPTIONS = [
  { label: "업종 전체", code: "" },
  { label: "제조업", code: "C" },
  { label: "농업", code: "01" },
  { label: "건설업", code: "F" },
  { label: "부동산업", code: "68" },
  { label: "숙박업", code: "55" },
  { label: "소프트웨어 개발·공급업", code: "58222" },
];

// [2026-09-09] announcements.regions 실제 distinct 값(시/도 단위) 전체. 구 단위는
// extract_region.py가 의도적으로 안 뽑음(오탐 위험 - 팀 결정, docs 참고).
const REGION_OPTIONS = [
  "지역 전체",
  "서울특별시",
  "경기도",
  "인천광역시",
  "부산광역시",
  "대구광역시",
  "광주광역시",
  "대전광역시",
  "울산광역시",
  "세종특별자치시",
  "강원특별자치도",
  "충청북도",
  "충청남도",
  "전라북도",
  "전북특별자치도",
  "전라남도",
  "전남광주통합특별시",
  "경상북도",
  "경상남도",
  "제주특별자치도",
  "비수도권(수도권 제외 전체)",
];

const SORT_OPTIONS = [
  { label: "최근 등록순", value: "recent" },
  { label: "마감임박순", value: "deadline" },
];

function MatchingList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [announcements, setAnnouncements] = useState<AnnouncementCardData[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  // [2026-09-10] region/ksic/sort도 로컬 state가 아니라 URL 쿼리로 옮김 - 로컬 state였을 땐
  // "필터" 팝업(다른 라우트)에 갔다 오면 MatchingList가 언마운트/리마운트되면서 초기화돼서,
  // 지역/업종/정렬 골라둔 게 필터 팝업 갔다오면 풀리는 버그가 있었음.
  const ksic = searchParams.get("ksic") ?? "";
  const region = searchParams.get("region") ?? "";
  const sort = searchParams.get("sort") ?? "recent";
  // FilterPage("전체 필터" 팝업)의 "적용하기"가
  // /matching?company=...&field=...&biz_age=...&age=... 형태로 넘겨준다.
  const company = searchParams.get("company") ?? "";
  const field = searchParams.get("field") ?? "";
  const bizAge = searchParams.get("biz_age") ?? "";
  const age = searchParams.get("age") ?? "";

  // 지역/업종/정렬 드롭다운 값 변경 - 다른 쿼리 파라미터(필터 팝업 값 등)는 그대로 두고
  // 이 키 하나만 갱신(없으면 삭제)한다.
  const updateParam = (key: string, value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      return next;
    });
  };

  const fetchPage = (offset: number, onDone: (body: MatchingListResponse) => void) =>
    fetch(
      `${API_BASE_URL}/api/matching?offset=${offset}&limit=${PAGE_SIZE}&ksic=${ksic}` +
        `&region=${encodeURIComponent(region)}&company=${encodeURIComponent(company)}` +
        `&field=${encodeURIComponent(field)}&biz_age=${encodeURIComponent(bizAge)}` +
        `&age=${encodeURIComponent(age)}&sort=${sort}`,
    )
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
    setLoading(true);
    // 필터가 바뀌면 이전 결과를 바로 지운다 - 안 그러면 새 결과가 올 때까지
    // 이전 필터의 카드가 화면에 남아있어서 그걸 눌러 엉뚱한 공고로 들어갈 수 있다.
    setAnnouncements([]);
    fetchPage(0, (body) => {
      setAnnouncements(body.data ?? []);
      setHasMore(body.has_more ?? false);
      setTotal(body.total ?? 0);
    }).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ksic, region, company, field, bizAge, age, sort]);

  const handleClearFilters = () => {
    setSearchParams({});
  };

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

  const handleFilterClick = () => {
    // 지금 적용 중인 필터(company/field/biz_age/age)를 그대로 들고 들어가서,
    // FilterPage가 열릴 때 칩 선택 상태를 복원할 수 있게 한다.
    navigate(`/matching/filter?${searchParams.toString()}`);
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

      {/* 필터바: 지역/업종/정렬 드롭다운 + 상세 필터 버튼, 전부 실동작 */}
      <div className={styles.filterBar}>
        <select
          className={styles.dropdownChip}
          value={region}
          onChange={(e) => updateParam("region", e.target.value === "지역 전체" ? "" : e.target.value)}
        >
          {REGION_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          className={styles.dropdownChip}
          value={ksic}
          onChange={(e) => updateParam("ksic", e.target.value)}
        >
          {KSIC_OPTIONS.map((opt) => (
            <option key={opt.code} value={opt.code}>
              {opt.label}
            </option>
          ))}
        </select>
        <select
          className={styles.dropdownChip}
          value={sort}
          onChange={(e) => updateParam("sort", e.target.value)}
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
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
        {company || bizAge ? (
          <p className={styles.guide}>
            필터 적용됨:{" "}
            {[company && `기업유형 ${company.split(",").join(", ")}`, bizAge && `업력 ${bizAge}`]
              .filter(Boolean)
              .join(" · ")}{" "}
            <button type="button" className={styles.clearFilterLink} onClick={handleClearFilters}>
              해제
            </button>
          </p>
        ) : (
          <p className={styles.guide}>
            필터를 누르면 기업유형·업력 등 필터를 더 설정할 수 있어요
          </p>
        )}

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
