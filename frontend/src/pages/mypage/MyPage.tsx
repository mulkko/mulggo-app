import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/myPage.module.css";
import logo from "../../assets/logo.svg";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";
import { authHeaders, getUserId, logout } from "../../auth/session";
import { downloadFilledDocument } from "../../utils/downloadFilledDoc";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 로그인 세션(getUserId)이 없을 때만 쓰는 폴백 - 자동로그인(.env) 미설정 환경 등 (ProfileEdit.tsx와 동일 사유).
const FALLBACK_USER_ID = 27;

interface ProfileSummary {
  name: string;
  profile_type: string | null;
  regions: string[] | null;
}

/**
 * 마이페이지 화면.
 *
 * 프로필 요약 + 나의 분석 리포트 / 관심있는 지원사업 / 채우기 이용내역 / 나의 지원내역
 * 4개 섹션 + 하단 공통 BottomNav("마이페이지" 탭 활성).
 *
 * [2026-09-09] 프로필 요약(이름/유형/지역)만 backend/api/mypage.py 실데이터로 교체함.
 * [2026-09-10] user_id를 로그인 세션(auth/session.ts::getUserId)에서 가져오도록 교체,
 * 세션 없으면 FALLBACK_USER_ID로 동작(ProfileEdit.tsx 참고).
 * [2026-09-10] 관심있는 지원사업(찜하기)도 backend/api/mypage.py(GET /bookmarks) +
 * backend/api/matching.py(POST·DELETE .../bookmark) 실데이터로 교체함 - 이 섹션만
 * 세션 토큰(authHeaders) 기준이라 비로그인이면 빈 목록으로 보인다.
 * [2026-09-10] 채우기 이용내역도 backend/api/mypage.py(GET /fill-history) +
 * backend/api/matching.py(GET .../fill, 성공 시 applications에 이력만 남김 - 파일
 * 자체는 저장 안 함) 실데이터로 교체함. 항목 클릭 시 utils/downloadFilledDoc.ts로
 * 그 자리에서 다시 채워서 다운로드(재생성) - 실패하면 에러 문구 표시. 공고가
 * 마감됐어도 개인 기록이라 목록에서 안 지우고 카드에 "공고마감" 오버레이만 표시
 * (마감된 공고도 원본 첨부는 며칠간 정상 응답 확인함, 다만 장기 보장은 안 됨이라
 * 다운로드 실패 시 에러 메시지로 자연스럽게 안내되게 함 - 사용자 확인, 2026-09-10).
 * [2026-09-10] 애초엔 분석 리포트/지원내역 대응 테이블이 실제로 0건이라(idea_refinement_
 * sessions/apply_status - fetch해도 항상 빈 배열) API 연동 자체를 안 만들고, 빈 배열로
 * 시작해서 각 섹션에 안내 문구("~이 없습니다")만 보여줬다. 더미데이터는 MyPage.tsx.bak에
 * 남겨뒀다.
 * [2026-09-12] 분석 리포트는 실제로 채워지기 시작해서(backend/api/diagnosis.py의
 * POST /api/diagnosis/start가 idea_refinement_sessions에 저장) backend/api/
 * mypage.py(GET /reports) 연동함(사용자 확인).
 * [2026-09-14] 지원내역도 연동함 - MatchingDetail.tsx "지원하기" 버튼이 이제 실제로
 * apply_status에 저장하도록 backend/api/matching.py에 POST·DELETE .../apply를
 * 추가했고, backend/api/mypage.py GET /apply-status로 목록을 받아온다(사용자 확인).
 *
 * 삭제(X) 버튼은 채우기 이용내역만 "로컬 state에서 해당 항목 제거"하는 임시 동작
 * (새로고침하면 사라짐) - 실제 서버 삭제 API는 없음. 관심있는 지원사업/지원내역은
 * 실연동이라 삭제 시 서버에도 반영된다. 화면 이동은 TODO 주석으로만 표시.
 *
 * 삭제 state 구조: 삭제 가능한 섹션마다 별도의 useState 배열을 두고,
 * 삭제 시 `setX(prev => prev.filter(item => item.id !== id))` 로 해당 id만 걸러낸다.
 * 관심 지원사업 카드는 공고 리스트와 동일한 공통 컴포넌트 AnnouncementCard 를 재사용한다.
 *
 * [2026-09-14] "나의 분석 리포트"를 제외한 3개 섹션(관심있는 지원사업/채우기 이용내역/
 * 나의 지원내역)의 삭제(X) 버튼을 "삭제 확인 팝업 → 확인 시 실제 삭제 + 완료 토스트"
 * 흐름으로 교체함(사용자 확인, 시나리오 보드 19/20번 기준). confirmTarget(section/id/label)
 * 하나로 3개 섹션 팝업을 공용 처리하고, 확인 시 섹션별 삭제 함수(handleConfirmDelete
 * 내부 분기)를 실행 - 관심있는 지원사업은 기존 실연동 DELETE 그대로, 채우기 이용내역은
 * 새로 만든 DELETE /api/mypage/fill-history/:id, 나의 지원내역은 DELETE
 * /api/mypage/apply-history/:id(대응 테이블 apply_status, PK submission_id - describe_table로
 * 실측 확인, schema.sql엔 없음)를 호출한다. 셋 다 실패해도 화면에서는 이미 지운 채로
 * 둔다(fire-and-forget, 일회성 서비스라 재시도/롤백 불필요 - 사용자 확인). 토스트는
 * MatchingDetail.tsx의 .toast 패턴(1.5초 후 자동 소멸) 재사용. 나의 지원내역은 목록
 * 조회(GET) 자체가 아직 없어(사용자 확인, 범위 밖) applyHistory가 항상 빈 배열이라
 * 삭제 핸들러/팝업 연결은 만들어뒀지만 화면에서 확인은 안 됨.
 */

interface AnalysisReport {
  id: string;
  /** 업종명 (예: "숙박 및 음식점업 (커피 전문점)") */
  industry: string;
  /** "업종코드 {코드} · {동} 주변 상권 동향"(카페형) 또는 "업종코드 {코드} · 업종 및
   * 특허 분석 지표"(기술창업형) - backend/api/mypage.py::list_reports 참고 */
  summary: string;
  /** 생성일 문구 */
  createdAt: string;
}

interface FillHistoryItem {
  id: string;
  title: string;
  fileName: string;
  attachmentId: number;
  /** 공고가 이미 마감됐는지 - 삭제/숨김 안 하고 오버레이로만 표시(사용자 확인) */
  expired: boolean;
  /** 채운 날짜 (YYYY.MM.DD) */
  exportedAt: string;
}

interface ApplyHistoryItem {
  id: string;
  title: string;
  /** 상태 뱃지 문구 (예: "지원함") */
  status: string;
  /** 지원일 (YYYY.MM.DD) */
  date: string;
}


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

/** 삭제 확인 팝업 (시나리오 보드 19번, 문구만 수정) — 관심있는 지원사업/채우기 이용내역/
 * 나의 지원내역 3개 섹션이 공용으로 쓴다. `label`이 문구의 "나의 {리스트명}"에 들어간다. */
function ConfirmDeleteModal({
  label,
  onCancel,
  onConfirm,
}: {
  label: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className={styles.confirmOverlay}>
      <div className={styles.confirmCard}>
        <p className={styles.confirmText}>
          이 공고를 삭제할까요?
          <br />
          나의 {label}에서 사라지고, 다시 불러올 수 없어요.
        </p>
        <div className={styles.confirmButtons}>
          <button type="button" className={styles.confirmCancelBtn} onClick={onCancel}>
            취소
          </button>
          <button type="button" className={styles.confirmDeleteBtn} onClick={onConfirm}>
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}

function MyPage() {
  const navigate = useNavigate();

  // 삭제 가능한 섹션마다 별도 로컬 state - 초기값은 빈 배열, 아래 useEffect가 각자
  // 실제 API로 채운다(분석 리포트/지원내역도 2026-09-12/2026-09-14에 연동 완료).
  const [reports, setReports] = useState<AnalysisReport[]>([]);
  const [interests, setInterests] = useState<AnnouncementCardData[]>([]);
  const [fillHistory, setFillHistory] = useState<FillHistoryItem[]>([]);
  const [applyHistory, setApplyHistory] = useState<ApplyHistoryItem[]>([]);
  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [fillError, setFillError] = useState("");

  // 삭제 확인 팝업 대상 - 3개 섹션(interest/fill/apply) 공용. label은 팝업/토스트 문구의
  // "나의 {리스트명}"에 그대로 들어간다(섹션 제목과 동일 문구).
  const [confirmTarget, setConfirmTarget] = useState<{
    section: "interest" | "fill" | "apply";
    id: string;
    label: string;
  } | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/mypage/profile?user_id=${getUserId() ?? FALLBACK_USER_ID}`)
      .then((res) => res.json())
      .then((res: { success: boolean; data?: ProfileSummary }) => {
        if (res.success && res.data) setProfile(res.data);
      })
      .catch(() => {
        /* 조회 실패 시 아래 더미 문구 그대로 표시 */
      });

    // [2026-09-10] 찜하기(bookmarks)/채우기 이용내역(fill-history) 연동 - 이 두
    // 엔드포인트는 위 프로필과 달리 세션 토큰(authHeaders)으로 로그인 사용자를
    // 구분한다. 비로그인이면 401 → 빈 목록 그대로.
    fetch(`${API_BASE_URL}/api/mypage/bookmarks`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((res: { success: boolean; data?: AnnouncementCardData[] }) => {
        if (res.success && res.data) setInterests(res.data);
      })
      .catch(() => {
        /* 조회 실패 시 빈 목록 그대로 */
      });

    fetch(`${API_BASE_URL}/api/mypage/fill-history`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((res: { success: boolean; data?: FillHistoryItem[] }) => {
        if (res.success && res.data) setFillHistory(res.data);
      })
      .catch(() => {
        /* 조회 실패 시 빈 목록 그대로 */
      });

    // [2026-09-12] 분석 리포트도 실데이터 연동함 - idea_refinement_sessions에 상권/
    // 기술창업 분석이 저장되기 시작해서(backend/api/diagnosis.py::start_diagnosis)
    // 더 이상 항상 빈 배열이 아니다. 위 두 섹션과 동일하게 로그인 세션 기준.
    fetch(`${API_BASE_URL}/api/mypage/reports`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((res: { success: boolean; data?: AnalysisReport[] }) => {
        if (res.success && res.data) setReports(res.data);
      })
      .catch(() => {
        /* 조회 실패 시 빈 목록 그대로 */
      });

    // [2026-09-14] 지원내역도 실데이터 연동함 - apply_status가 채워지기 시작해서
    // (backend/api/matching.py::set_applied, MatchingDetail.tsx "지원하기" 토글)
    // 더 이상 항상 빈 배열이 아니다. 위 섹션들과 동일하게 로그인 세션 기준.
    fetch(`${API_BASE_URL}/api/mypage/apply-status`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((res: { success: boolean; data?: ApplyHistoryItem[] }) => {
        if (res.success && res.data) setApplyHistory(res.data);
      })
      .catch(() => {
        /* 조회 실패 시 빈 목록 그대로 */
      });
  }, []);

  const removeById =
    <T extends { id: string }>(setter: React.Dispatch<React.SetStateAction<T[]>>) =>
    (id: string) =>
      setter((prev) => prev.filter((item) => item.id !== id));

  const handleContactClick = () => {
    navigate("/support");
  };

  const handleProfileClick = () => {
    navigate("/mypage/edit");
  };

  const handleNewAnalysisClick = () => {
    // TODO: 새 분석(사업 구체화 챗봇) 시작 화면으로 이동
  };

  const handleReportClick = (id: string) => {
    navigate(`/diagnosis/report/${id}`);
  };

  const handleViewAllInterests = () => {
    navigate("/matching");
  };

  const handleInterestCardClick = (item: AnnouncementCardData) => {
    navigate(`/matching/${item.id}`);
  };

  // 3개 섹션(interest/fill/apply) 공용 - X 버튼은 바로 지우지 않고 확인 팝업부터 띄운다.
  const handleRequestDelete = (
    section: "interest" | "fill" | "apply",
    id: string,
    label: string
  ) => {
    setConfirmTarget({ section, id, label });
  };

  // 확인 팝업에서 "삭제"를 눌렀을 때만 실제로 지운다. 실패해도 화면에선 이미 지운
  // 채로 둔다(fire-and-forget) - 일회성 서비스라 엄격한 재시도/롤백은 불필요(사용자 확인).
  const handleConfirmDelete = () => {
    if (!confirmTarget) return;
    const { section, id, label } = confirmTarget;

    if (section === "interest") {
      removeById(setInterests)(id);
      fetch(`${API_BASE_URL}/api/matching/${id}/bookmark`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {
        /* 실패해도 화면에선 이미 지운 채로 둔다 - 다음 진입 시 서버 목록으로 다시 맞춰짐 */
      });
    } else if (section === "fill") {
      removeById(setFillHistory)(id);
      fetch(`${API_BASE_URL}/api/mypage/fill-history/${id}`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {
        /* 실패해도 화면에선 이미 지운 채로 둔다 */
      });
    } else {
      // [2026-09-14] apply-status 목록의 id는 submission_id가 아니라 announcement_id라
      // (backend/api/mypage.py::list_apply_status 참고) 삭제도 같은 키를 쓰는
      // matching.py의 지원취소 엔드포인트를 호출해야 한다(MatchingDetail.tsx "지원하기"
      // 토글의 DELETE와 동일 - 행을 지우지 않고 is_applied만 false로 바꿔서 다시 안 나타남).
      removeById(setApplyHistory)(id);
      fetch(`${API_BASE_URL}/api/matching/${id}/apply`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {
        /* 실패해도 화면에선 이미 지운 채로 둔다 */
      });
    }

    setConfirmTarget(null);
    setToastMessage(`나의 ${label}에서 삭제됐어요.`);
    setTimeout(() => setToastMessage(null), 1500);
  };

  const handleFillHistoryClick = async (item: FillHistoryItem) => {
    setFillError("");
    const error = await downloadFilledDocument(item.attachmentId, item.fileName);
    if (error) setFillError(error);
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 1. 헤더: "MULKKO PAGE" 로고 + 우측 고객센터 아이콘 */}
      <header className={styles.header}>
        <span className={styles.logo}>
          <span className={styles.logoText}>MULKKO PAGE</span>
          <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
        </span>
        <button
          type="button"
          className={styles.contactBtn}
          aria-label="1:1 문의"
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
            <span className={styles.profileName}>{profile ? `${profile.name} 님` : "김창업 님"}</span>
            <span className={styles.profileSub}>
              {profile
                ? [profile.profile_type, profile.regions?.join(", ") || null].filter(Boolean).join(" · ") || "정보 없음"
                : "예비창업자 · 서울특별시"}
            </span>
          </span>
          <span className={styles.profileArrow} aria-hidden="true">
            ›
          </span>
        </button>

        {/* 3. 나의 분석 리포트 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>나의 분석 리포트</h2>
          {reports.length === 0 && <p className={styles.emptyText}>분석한 리포트가 없습니다</p>}
          {reports.map((report) => (
            <div key={report.id} className={styles.reportCard}>
              <button
                type="button"
                className={styles.reportBody}
                onClick={() => handleReportClick(report.id)}
              >
                <span className={styles.reportIndustry}>{report.industry}</span>
                <span className={styles.reportSummary}>{report.summary}</span>
                <span className={styles.reportDate}>{report.createdAt} 생성</span>
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
            {interests.length > 0 && (
              <button
                type="button"
                className={styles.viewAllBtn}
                onClick={handleViewAllInterests}
              >
                전체보기 →
              </button>
            )}
          </div>
          {interests.length === 0 && <p className={styles.emptyText}>관심있는 지원사업이 없습니다</p>}
          {interests.map((item) => (
            <AnnouncementCard
              key={item.id}
              item={item}
              onClick={handleInterestCardClick}
              onDelete={(itemId) => handleRequestDelete("interest", itemId, "관심있는 지원사업")}
            />
          ))}
        </section>

        {/* 5. 채우기 이용내역 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>채우기 이용내역</h2>
          {fillError && <p className={styles.fillErrorText}>{fillError}</p>}
          {fillHistory.length === 0 && <p className={styles.emptyText}>채우기 이용내역이 없습니다</p>}
          {fillHistory.map((item) => (
            <div key={item.id} className={styles.fillCard}>
              <button
                type="button"
                className={styles.fillBody}
                onClick={() => handleFillHistoryClick(item)}
              >
                <span className={styles.fillTitle}>{item.title}</span>
                <span className={styles.fillDesc}>{item.fileName}</span>
                <span className={styles.fillBadge}>{item.exportedAt} 채움</span>
              </button>
              {item.expired && (
                <div className={styles.fillExpiredOverlay} aria-hidden="true">
                  <span className={styles.fillExpiredTitle}>공고마감</span>
                  <span className={styles.fillExpiredSub}>문서 다운로드는 가능합니다</span>
                </div>
              )}
              <DeleteButton
                onClick={() => handleRequestDelete("fill", item.id, "채우기 이용내역")}
              />
            </div>
          ))}
        </section>

        {/* 6. 나의 지원내역 */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>나의 지원내역</h2>
          {applyHistory.length === 0 && <p className={styles.emptyText}>지원하신 내역이 존재하지 않습니다</p>}
          {applyHistory.map((item) => (
            <div key={item.id} className={styles.applyCard}>
              <span className={styles.applyTitle}>{item.title}</span>
              <span className={styles.applyMeta}>
                <span className={styles.applyStatus}>{item.status}</span>
                <span className={styles.applyDate}>{item.date}</span>
              </span>
              <DeleteButton
                onClick={() => handleRequestDelete("apply", item.id, "나의 지원내역")}
              />
            </div>
          ))}
        </section>

        {/* 7. 푸터 - 로그아웃 */}
        <div className={styles.footer}>
          <button type="button" className={styles.logoutBtn} onClick={handleLogout}>
            로그아웃
          </button>
        </div>
      </div>

      <ChatFab variant="withBottomNav" />

      {/* 8. 하단 네비게이션 ("마이페이지" 탭 활성) */}
      <BottomNav active="my" />

      {confirmTarget && (
        <ConfirmDeleteModal
          label={confirmTarget.label}
          onCancel={() => setConfirmTarget(null)}
          onConfirm={handleConfirmDelete}
        />
      )}

      {toastMessage && (
        <div className={styles.toast} role="status">
          {toastMessage}
        </div>
      )}
    </div>
  );
}

export default MyPage;
