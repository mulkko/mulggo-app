import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import styles from "../../styles/matchingList.module.css";
import logo from "../../assets/logo.svg";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import { authHeaders } from "../../auth/session";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";

/**
 * 지원사업 매칭 리스트(공고 리스트) 화면.
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
 *
 * [2026-09-12] 매칭/업종무관 두 섹션의 화면 디자인을 MatchingListDraft.tsx(팀원 검토용
 * 사본)의 "업종 맞춤 공고 / 업종 무관 공고" 섹션 제목+안내문구 스타일로 교체함(사용자
 * 확인) - 데이터 조회/두 섹션 각자 독립적인 페이지네이션 등 기능 로직은 그대로.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
// [2026-09-10] 한 화면에 카드가 너무 많이 보인다는 피드백 - 처음엔 8개만 보여주고,
// "더보기" 누를 때마다 12개씩 추가로 불러온다(기존엔 둘 다 20개였음).
const INITIAL_PAGE_SIZE = 8;
const LOAD_MORE_PAGE_SIZE = 12;
// [2026-09-12] 업종무관/특정불가 섹션은 참고용이라 매칭 섹션(8개)보다 더 적게,
// 6개만 기본으로 보여주고 "더보기"로 나머지를 불러온다(사용자 확인).
const INITIAL_PAGE_SIZE_UNCLASSIFIED = 6;

// [2026-09-10] 상세 화면 갔다가 뒤로가기로 돌아오면 "더보기"로 불러온 만큼은
// 유지해야 한다는 요구사항 - 필터 쿼리별로 마지막에 로드된 개수를 세션에 저장해두고,
// 돌아왔을 때(같은 쿼리면) 그 개수만큼 한 번에 다시 불러온다(탭 닫으면 초기화되는
// sessionStorage면 충분 - 새로고침/새 탭까지 유지할 필요는 없음).
const LIST_STATE_KEY = "mulkko_matching_list_state";

// [2026-09-12] 매칭 섹션 + 업종무관/특정불가 섹션 두 개로 나뉘면서, "더보기"로 불러온
// 개수도 두 섹션 각각 따로 기억해야 한다 - count/unclassifiedCount 둘 다 저장.
function readSavedCount(query: string): { count: number; unclassifiedCount: number } | null {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { query: string; count: number; unclassifiedCount?: number };
    return saved.query === query ? { count: saved.count, unclassifiedCount: saved.unclassifiedCount ?? 0 } : null;
  } catch {
    return null;
  }
}

function saveListState(query: string, count: number, unclassifiedCount: number): void {
  try {
    sessionStorage.setItem(LIST_STATE_KEY, JSON.stringify({ query, count, unclassifiedCount }));
  } catch {
    // 프라이빗 모드 등 sessionStorage 못 쓰는 환경 - 조용히 무시(더보기 상태 유지만 안 될 뿐).
  }
}

type MatchingListResponse = {
  success: boolean;
  data?: AnnouncementCardData[];
  has_more?: boolean;
  total?: number;
  // [2026-09-12] ksic 필터가 있을 때만 내려오는 두 번째 섹션 - "업종무관"/"특정불가"라
  // ksic_codes_matched가 원래 비어있어서 위 매칭 섹션에서 자연히 빠지는 공고들
  // (backend/api/matching.py list_announcements() 독스트링 참고).
  unclassified?: AnnouncementCardData[];
  unclassified_has_more?: boolean;
  unclassified_total?: number;
};

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
const SORT_SHEET_OPTIONS: SheetOption[] = SORT_OPTIONS;

interface KsicOption {
  code: string;
  name: string;
  largeCode: string;
  largeName: string;
}

// 업종 드롭다운의 기본(진단에서 안 온 일반 진입) 옵션이 로딩 전이거나 실패했을 때
// 최소한 "업종 전체"는 눌러볼 수 있게 - DEFAULT_KSIC_FALLBACK 하나만 둔다.
const DEFAULT_KSIC_FALLBACK: SheetOption[] = [{ label: "업종 전체", value: "" }];

function MatchingList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [announcements, setAnnouncements] = useState<AnnouncementCardData[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  // [2026-09-12] "업종무관"/"특정불가" 공고 섹션 - 매칭 섹션과 완전히 독립적인 자기
  // 페이지네이션(offset/limit/더보기)을 가진다(사용자 확인 - 기본 형식, 전체를 한
  // 화면에 두 섹션으로 나눠서 각자 더보기).
  const [unclassifiedAnnouncements, setUnclassifiedAnnouncements] = useState<AnnouncementCardData[]>([]);
  const [unclassifiedTotal, setUnclassifiedTotal] = useState(0);
  const [unclassifiedHasMore, setUnclassifiedHasMore] = useState(false);
  const [loadingMoreUnclassified, setLoadingMoreUnclassified] = useState(false);
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

  // [2026-09-12] 업종 드롭다운의 일반(진단 없이 바로 들어온) 기본 옵션 - 예전엔
  // 제조업/농업 등 6개만 하드코딩해서 "테스트용"으로 써왔는데(사용자 확인, 실제
  // 서비스에 테스트 데이터가 노출되면 안 됨), /api/ksic/options(전체 1,202건)에서
  // 대분류(21개, A~U)만 뽑아 "업종 전체" + 21개로 교체한다. 세세분류까지 다 보여주면
  // 항목이 너무 많아서 대분류 단위로 좁힌다.
  const [defaultKsicOptions, setDefaultKsicOptions] = useState<SheetOption[] | null>(null);
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/ksic/options`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: KsicOption[] }) => {
        if (!body.success || !body.data) return;
        const seen = new Map<string, string>();
        for (const o of body.data) {
          if (!seen.has(o.largeCode)) seen.set(o.largeCode, o.largeName);
        }
        setDefaultKsicOptions([
          { label: "업종 전체", value: "" },
          ...[...seen.entries()].map(([code, name]) => ({ label: name, value: code })),
        ]);
      })
      .catch(() => setDefaultKsicOptions(null));
  }, []);

  // [2026-09-11] 사업구체화 진단(DiagnosisReport/DiagnosisStep9)에서 "지원사업 보러가기"로
  // 넘어오면 ksic 쿼리에 진단이 매칭한 KSIC코드(들)가 실린다 - 이 경우 업종 드롭다운은
  // 위 기본 대분류 목록 대신 "그 매칭된 업종들만" 보여줘야 한다(사용자 확인). 대분류
  // 코드는 항상 알파벳 한 글자(A~U)라, 그게 아니면(숫자로 된 세세분류 코드) 진단발
  // 진입으로 보고 /api/ksic/options에서 해당 코드들만 걸러 이름을 붙인다.
  const [matchedKsicOptions, setMatchedKsicOptions] = useState<SheetOption[] | null>(null);
  // 진단에서 넘어온 코드 목록은 화면 진입 시점(최초 ksic 값) 기준으로 한 번만 고정한다 -
  // 안 그러면 사용자가 그 목록 중 하나로 좁혀 고를 때마다 ksic이 바뀌면서 "매칭된 업종
  // 전체" 기준 자체가 방금 고른 그 하나로 줄어드는 문제가 생긴다.
  const initialMatchedCodesRef = useRef<string[] | null>(null);
  useEffect(() => {
    if (initialMatchedCodesRef.current !== null) return; // 이미 한 번 판정함
    const codes = ksic.split(",").map((c) => c.trim()).filter(Boolean);
    const isLargeCategoryCode = (c: string) => /^[A-Z]$/.test(c);
    const isKnownOption = codes.length > 0 && codes.every(isLargeCategoryCode);
    initialMatchedCodesRef.current = codes.length > 0 && !isKnownOption ? codes : [];
    if (initialMatchedCodesRef.current.length === 0) return;

    fetch(`${API_BASE_URL}/api/ksic/options`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: KsicOption[] }) => {
        if (!body.success || !body.data) return;
        const codesNow = initialMatchedCodesRef.current ?? [];
        const matched = body.data.filter((o) => codesNow.includes(o.code));
        // [2026-09-12, 버그 수정] 매칭된 코드가 1개뿐이면 "매칭된 업종 전체"의 value(그
        // 코드 하나)와 아래 개별 항목의 value가 완전히 같은 문자열이 된다 - 라디오는
        // opt.value === 현재값으로 활성 여부를 판정하는데, 값이 같은 행이 2개 있으면
        // 라디오(단일선택) 구조에서도 둘 다 활성으로 보인다(체크박스처럼 보이는 원인).
        // 코드가 1개뿐이면 "전체"와 "그 하나"가 어차피 같은 의미라 "전체" 행 자체를
        // 빼서 중복을 없앤다.
        setMatchedKsicOptions([
          ...(codesNow.length > 1 ? [{ label: "매칭된 업종 전체", value: codesNow.join(",") }] : []),
          ...matched.map((o) => ({ label: o.name, value: o.code })),
        ]);
      })
      .catch(() => setMatchedKsicOptions(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // [2026-09-12] 매칭 섹션/업종무관 섹션 각자 자기 offset/limit을 갖는다 - 한쪽만
  // "더보기"로 늘릴 때는 다른 쪽 limit을 0으로 보내 그쪽 데이터는 그냥 무시한다
  // (백엔드가 항상 두 섹션을 같이 계산해 내려주므로, 필요없는 쪽만 응답에서 안 쓰면 됨 -
  // 별도 엔드포인트를 만들 필요가 없어서 이 편이 더 간단하다).
  const fetchPage = (
    offset: number, limit: number, unclassifiedOffset: number, unclassifiedLimit: number,
    onDone: (body: MatchingListResponse) => void,
  ) =>
    fetch(
      `${API_BASE_URL}/api/matching?offset=${offset}&limit=${limit}` +
        `&unclassified_offset=${unclassifiedOffset}&unclassified_limit=${unclassifiedLimit}` +
        `&ksic=${ksic}&region=${encodeURIComponent(region)}&company=${encodeURIComponent(company)}` +
        `&field=${encodeURIComponent(field)}&biz_age=${encodeURIComponent(bizAge)}` +
        `&age=${encodeURIComponent(age)}&sort=${sort}`,
      { headers: authHeaders() },
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
    setUnclassifiedAnnouncements([]);
    const query = searchParams.toString();
    const saved = readSavedCount(query);
    const initialLimit = saved && saved.count > INITIAL_PAGE_SIZE ? saved.count : INITIAL_PAGE_SIZE;
    const initialUnclassifiedLimit =
      saved && saved.unclassifiedCount > INITIAL_PAGE_SIZE_UNCLASSIFIED
        ? saved.unclassifiedCount
        : INITIAL_PAGE_SIZE_UNCLASSIFIED;
    fetchPage(0, initialLimit, 0, initialUnclassifiedLimit, (body) => {
      setAnnouncements(body.data ?? []);
      setHasMore(body.has_more ?? false);
      setTotal(body.total ?? 0);
      setUnclassifiedAnnouncements(body.unclassified ?? []);
      setUnclassifiedHasMore(body.unclassified_has_more ?? false);
      setUnclassifiedTotal(body.unclassified_total ?? 0);
      saveListState(query, (body.data ?? []).length, (body.unclassified ?? []).length);
    }).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ksic, region, company, field, bizAge, age, sort]);

  const handleClearFilters = () => {
    setSearchParams({});
  };

  const handleLoadMore = () => {
    setLoadingMore(true);
    const query = searchParams.toString();
    fetchPage(announcements.length, LOAD_MORE_PAGE_SIZE, unclassifiedAnnouncements.length, 0, (body) => {
      setAnnouncements((prev) => {
        const next = [...prev, ...(body.data ?? [])];
        saveListState(query, next.length, unclassifiedAnnouncements.length);
        return next;
      });
      setHasMore(body.has_more ?? false);
    }).finally(() => setLoadingMore(false));
  };

  const handleLoadMoreUnclassified = () => {
    setLoadingMoreUnclassified(true);
    const query = searchParams.toString();
    fetchPage(announcements.length, 0, unclassifiedAnnouncements.length, LOAD_MORE_PAGE_SIZE, (body) => {
      setUnclassifiedAnnouncements((prev) => {
        const next = [...prev, ...(body.unclassified ?? [])];
        saveListState(query, announcements.length, next.length);
        return next;
      });
      setUnclassifiedHasMore(body.unclassified_has_more ?? false);
    }).finally(() => setLoadingMoreUnclassified(false));
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

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* [2026-09-13, 사용자 확인] "<" 뒤로가기 버튼 추가(다른 MULKKO 화면들과 동일
          레이아웃) + "물꼬 분석" 링크는 삭제(사용자 확인) */}
      <header className={styles.header}>
        <span className={styles.headerLeft}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.logo}>
            <span className={styles.logoText}>MULKKO MATCHING</span>
            <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
          </span>
        </span>
      </header>

      {/* 필터바: 지역/업종/정렬 칩(누르면 시트 팝업, SelectSheet variant="chip") + 상세 필터 버튼 */}
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
          className={styles.dropdownChip}
          label="업종"
          name="ksic"
          value={ksic}
          options={matchedKsicOptions ?? defaultKsicOptions ?? DEFAULT_KSIC_FALLBACK}
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

      {/* 스크롤 영역: 안내 문구 + 카운트 박스 + 카드 리스트(업종맞춤/업종무관 2그룹) */}
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
          {/* [2026-09-13] 업종코드 필터가 걸려있으면(분석 리포트에서 넘어온 경우) 업종
              맞춤 섹션(total)만이 아니라 업종무관 섹션(unclassifiedTotal)까지 합친 값을
              보여준다(사용자 확인) - 필터 없을 땐 unclassifiedTotal이 0이라 total 그대로. */}
          <span className={styles.countValue}>{total + unclassifiedTotal}건</span>
        </div>

        {loading && <p className={styles.guide}>불러오는 중...</p>}
        {error && <p className={styles.guide}>{error}</p>}

        {announcements.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionTitle}>업종 맞춤 공고</span>
              <span className={styles.sectionHint}>업종별로 보고 싶다면 업종 필터를 이용해주세요</span>
            </div>
            <ul className={styles.cardList}>
              {announcements.map((item) => (
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

        {/* [2026-09-12] 업종무관/특정불가 섹션 - ksic 필터가 걸려 매칭 섹션과 분리된
            경우에만 응답에 딸려온다. 로드된 게 하나도 없으면(0건) 섹션 자체를 안 보여준다.
            매칭 섹션과 완전히 독립적인 자기 페이지네이션(더보기)을 그대로 유지. */}
        {unclassifiedAnnouncements.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionTitle}>업종 무관 공고</span>
              <span className={styles.sectionHint}>자세한 사항은 공고상세를 이용해주세요</span>
            </div>
            <ul className={styles.cardList}>
              {unclassifiedAnnouncements.map((item) => (
                <li key={item.id}>
                  <AnnouncementCard item={item} onClick={handleCardClick} />
                </li>
              ))}
            </ul>
            {unclassifiedHasMore && (
              <button
                type="button"
                className={styles.loadMoreButton}
                onClick={handleLoadMoreUnclassified}
                disabled={loadingMoreUnclassified}
              >
                {loadingMoreUnclassified ? "불러오는 중..." : "더보기"}
              </button>
            )}
          </div>
        )}
      </div>

      <ChatFab variant="withBottomNav" />

      <BottomNav active="matching" />
    </div>
  );
}

export default MatchingList;
