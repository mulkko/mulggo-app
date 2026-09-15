import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import styles from "../../styles/matchingListDraft.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import logo from "../../assets/logo.svg";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import BackButton from "../../components/BackButton/BackButton";

/**
 * [DRAFT] 지원사업 매칭 리스트(공고 리스트) 화면 - "업종맞춤/업종무관" 2그룹 분리 검토용 사본.
 *
 * 원본 /matching(MatchingList.tsx)은 다른 팀원이 같이 작업 중이라 건드리지 않고,
 * /matching-draft 라우트로 별도 복사해서 여기서만 실험한다. 원본과의 차이는
 * "카드 리스트를 업종맞춤/업종무관 두 섹션으로 나눠서 보여주는 것" 하나뿐 -
 * 그 외 헤더/필터바/카운트박스/하단네비/데이터 fetching 로직은 원본과 동일하다.
 *
 * 그룹 기준: item.ksicCodesMatched(선택한 업종 필터에 매칭된 업종코드, backend/api/matching.py)가
 * 비어있지 않으면 "업종 맞춤 공고", 비어있으면 "업종 무관 공고". 프로토타입
 * "15 공고 매칭 리스트"(is.match 키) 문구/스타일 그대로 반영 - 섹션 제목엔 카운트 배지 없음,
 * 섹션 사이 별도 구분선 없이 리스트 기본 gap(12px)만 적용됨.
 *
 * 자격이 맞는 정부지원사업을 카드 리스트로 보여준다. 상단에 지역/업종/정렬
 * 필터바가 있고, 하단에는 공통 BottomNav("매칭" 탭 활성).
 *
 * 목록은 GET /api/matching에서 가져온다. 지역/업종/정렬, "필터" 팝업
 * (기업유형/지원분야/업력/연령) 전부 실제 필터링이 반영됨.
 *
 * [2026-09-10] 지역/업종/정렬은 원래 네이티브 <select> 3개였는데, 화면 폭이 좁을 때
 * (예: 360px) select 3개 + 필터 버튼이 flex 한 줄에 안 들어가고 오른쪽이 밀려나가는
 * 문제가 있었음. 이 프로젝트는 common.css .pageContainer가 항상 최대 640px로
 * 고정이라(데스크톱 전용 레이아웃 없음, CLAUDE.md) 화면 크기로 분기하지 않고,
 * 셀렉트 대신 칩 버튼 + 하단 시트 팝업(라디오 버튼 목록)으로 화면 크기 상관없이
 * 통일함 (DocPreview.tsx 다운로드 모달과 같은 오버레이 패턴 재사용).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
// [2026-09-10] 한 화면에 카드가 너무 많이 보인다는 피드백 - 처음엔 8개만 보여주고,
// "더보기" 누를 때마다 12개씩 추가로 불러온다(기존엔 둘 다 20개였음).
const INITIAL_PAGE_SIZE = 8;
const LOAD_MORE_PAGE_SIZE = 12;

// [2026-09-10] 상세 화면 갔다가 뒤로가기로 돌아오면 "더보기"로 불러온 만큼은
// 유지해야 한다는 요구사항 - 필터 쿼리별로 마지막에 로드된 개수를 세션에 저장해두고,
// 돌아왔을 때(같은 쿼리면) 그 개수만큼 한 번에 다시 불러온다(탭 닫으면 초기화되는
// sessionStorage면 충분 - 새로고침/새 탭까지 유지할 필요는 없음).
const LIST_STATE_KEY = "mulkko_matching_list_state";

function readSavedCount(query: string): number | null {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { query: string; count: number };
    return saved.query === query ? saved.count : null;
  } catch {
    return null;
  }
}

function saveListState(query: string, count: number): void {
  try {
    sessionStorage.setItem(LIST_STATE_KEY, JSON.stringify({ query, count }));
  } catch {
    // 프라이빗 모드 등 sessionStorage 못 쓰는 환경 - 조용히 무시(더보기 상태 유지만 안 될 뿐).
  }
}

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

type SheetOption = { label: string; value: string };

// select 3개를 시트 팝업으로 통일하기 위한 {label, value} 정규화.
const REGION_SHEET_OPTIONS: SheetOption[] = REGION_OPTIONS.map((r) => ({
  label: r,
  value: r === "지역 전체" ? "" : r,
}));
const KSIC_SHEET_OPTIONS: SheetOption[] = KSIC_OPTIONS.map((o) => ({ label: o.label, value: o.code }));
const SORT_SHEET_OPTIONS: SheetOption[] = SORT_OPTIONS;

function MatchingListDraft() {
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

  // 지역/업종/정렬 칩 값 변경 - 다른 쿼리 파라미터(필터 팝업 값 등)는 그대로 두고
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


  const fetchPage = (offset: number, limit: number, onDone: (body: MatchingListResponse) => void) =>
    fetch(
      `${API_BASE_URL}/api/matching?offset=${offset}&limit=${limit}&ksic=${ksic}` +
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
    const query = searchParams.toString();
    const savedCount = readSavedCount(query);
    const initialLimit = savedCount && savedCount > INITIAL_PAGE_SIZE ? savedCount : INITIAL_PAGE_SIZE;
    fetchPage(0, initialLimit, (body) => {
      setAnnouncements(body.data ?? []);
      setHasMore(body.has_more ?? false);
      setTotal(body.total ?? 0);
      saveListState(query, (body.data ?? []).length);
    }).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ksic, region, company, field, bizAge, age, sort]);

  const handleClearFilters = () => {
    setSearchParams({});
  };

  const handleLoadMore = () => {
    setLoadingMore(true);
    const query = searchParams.toString();
    fetchPage(announcements.length, LOAD_MORE_PAGE_SIZE, (body) => {
      setAnnouncements((prev) => {
        const next = [...prev, ...(body.data ?? [])];
        saveListState(query, next.length);
        return next;
      });
      setHasMore(body.has_more ?? false);
    }).finally(() => setLoadingMore(false));
  };

  // [2026-09-13, 사용자 확인] 다른 MULKKO 화면들(레이아웃 공용 헤더)처럼 "<" 뒤로가기
  // 버튼 추가 - 이 화면은 탭 루트라 뒤로갈 이전 화면 개념이 없어서 홈으로 보낸다.
  const handleBack = () => navigate("/home");

  const handleFilterClick = () => {
    // 지금 적용 중인 필터(company/field/biz_age/age)를 그대로 들고 들어가서,
    // FilterPage가 열릴 때 칩 선택 상태를 복원할 수 있게 한다.
    navigate(`/matching/filter?${searchParams.toString()}`);
  };

  const handleCardClick = (item: AnnouncementCardData) => {
    // 공고 상세로 이동하면서 지금 적용 중인 필터 쿼리를 state로 같이 넘긴다 -
    // 상세 화면의 뒤로가기가 이 값으로 "/matching?<필터>"를 만들어 복귀한다.
    // (예전엔 navigate(-1)로 브라우저 history를 되돌렸는데, 상세 화면에 직접 링크로
    // 들어온 경우 등 history에 리스트가 없으면 안 먹는 문제가 있었음.)
    navigate(`/matching/${item.id}`, { state: { fromSearch: searchParams.toString() } });
  };

  // [DRAFT] "업종 맞춤 공고" / "업종 무관 공고" 2그룹 분리 - ksicCodesMatched(선택한 업종
  // 필터에 실제 매칭된 업종코드)가 있으면 맞춤, 없으면 무관으로 나눈다.
  const industryMatched = announcements.filter(
    (item) => (item.ksicCodesMatched?.length ?? 0) > 0,
  );
  const industryUnrelated = announcements.filter(
    (item) => (item.ksicCodesMatched?.length ?? 0) === 0,
  );

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* [2026-09-13, 사용자 확인] "<" 뒤로가기 버튼 추가 + "물꼬 분석" 링크 삭제 */}
      <header className={styles.header}>
        <span className={styles.headerLeft}>
          <BackButton onClick={handleBack} />
          <span className={styles.logo}>
            <span className={styles.logoText}>MULKKO MATCHING</span>
            <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
          </span>
        </span>
      </header>

      {/* 필터바: 지역/업종/정렬 칩(누르면 시트 팝업) + 상세 필터 버튼, 전부 실동작 */}
      <div className={styles.filterBar}>
        <SelectSheet
          variant="chip"
          className={styles.dropdownChip}
          label="지역"
          name="region"
          value={region}
          options={REGION_SHEET_OPTIONS}
          onChange={(v) => updateParam("region", v)}
        />
        <SelectSheet
          variant="chip"
          className={`${styles.dropdownChip} ${styles.ksicChip}`}
          label="업종"
          name="ksic"
          value={ksic}
          options={KSIC_SHEET_OPTIONS}
          onChange={(v) => updateParam("ksic", v)}
        />
        <SelectSheet
          variant="chip"
          className={styles.dropdownChip}
          label="정렬"
          name="sort"
          value={sort}
          options={SORT_SHEET_OPTIONS}
          onChange={(v) => updateParam("sort", v)}
        />
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

        {industryMatched.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionTitle}>업종 맞춤 공고</span>
              <span className={styles.sectionHint}>
                업종별로 보고 싶다면 업종 필터를 이용해주세요
              </span>
            </div>
            <ul className={styles.cardList}>
              {industryMatched.map((item) => (
                <li key={item.id}>
                  <AnnouncementCard item={item} onClick={handleCardClick} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {industryUnrelated.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionTitle}>업종 무관 공고</span>
              <span className={styles.sectionHint}>자세한 사항은 공고상세를 이용해주세요</span>
            </div>
            <ul className={styles.cardList}>
              {industryUnrelated.map((item) => (
                <li key={item.id}>
                  <AnnouncementCard item={item} onClick={handleCardClick} />
                </li>
              ))}
            </ul>
          </div>
        )}

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

export default MatchingListDraft;
