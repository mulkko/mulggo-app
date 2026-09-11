import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/myPage.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import AnnouncementCard, {
  type AnnouncementCardData,
} from "../../components/AnnouncementCard/AnnouncementCard";
import { authHeaders, clearSession, getUserId } from "../../auth/session";
import { downloadFilledDocument } from "../../utils/downloadFilledDoc";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// 로그인 세션(getUserId)이 없을 때만 쓰는 폴백 - 자동로그인(.env) 미설정 환경 등 (ProfileEdit.tsx와 동일 사유).
const FALLBACK_USER_ID = 27;

interface ProfileSummary {
  name: string;
  profile_type: string | null;
  region: string | null;
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
 * [2026-09-10] 나머지 2개 섹션(분석 리포트/지원내역)은 대응 테이블이 실제로 0건이라
 * (idea_refinement_sessions/apply_status - fetch해도 항상 빈 배열) API 연동 자체를
 * 안 만들고, 그냥 빈 배열로 시작해서 각 섹션에 안내 문구("~이 없습니다")만 보여준다
 * (사용자 확인). 더미데이터는 MyPage.tsx.bak에 남겨뒀다 - 나중에 진짜 테이블이
 * 채워지면 그 파일의 카드 모양을 참고해서 연동할 것.
 *
 * 삭제(X) 버튼은 "로컬 state에서 해당 항목 제거"만 하는 임시 동작(새로고침하면
 * 사라짐) - 실제 서버 삭제 API는 없음. 화면 이동은 TODO 주석으로만 표시.
 * (관심있는 지원사업은 위처럼 실연동이라 삭제 시 서버에서도 찜 해제됨.)
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

function MyPage() {
  const navigate = useNavigate();

  // 삭제 가능한 섹션마다 별도 로컬 state (백엔드 연동 전이라 새로고침 시 초기화됨)
  // [2026-09-10] 분석 리포트/지원내역은 대응 테이블이 실제로 0건이라(idea_refinement_
  // sessions/apply_status) API를 만들어도 항상 빈 배열이므로, 더미데이터 대신 처음부터
  // 빈 배열로 시작하고 각 섹션에 안내 문구를 보여준다(사용자 확인, 2026-09-10).
  // 채워지는 테이블이 생기면 그때 프로필/관심지원사업처럼 useEffect에서 fetch로 교체.
  const [reports, setReports] = useState<AnalysisReport[]>([]);
  const [interests, setInterests] = useState<AnnouncementCardData[]>([]);
  const [fillHistory, setFillHistory] = useState<FillHistoryItem[]>([]);
  const [applyHistory, setApplyHistory] = useState<ApplyHistoryItem[]>([]);
  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [fillError, setFillError] = useState("");

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

  const handleReportClick = (_id: string) => {
    // TODO: 해당 분석 리포트 상세 화면으로 이동
  };

  const handleViewAllInterests = () => {
    navigate("/matching");
  };

  const handleInterestCardClick = (item: AnnouncementCardData) => {
    navigate(`/matching/${item.id}`);
  };

  const handleRemoveInterest = (id: string) => {
    removeById(setInterests)(id);
    fetch(`${API_BASE_URL}/api/matching/${id}/bookmark`, {
      method: "DELETE",
      headers: authHeaders(),
    }).catch(() => {
      /* 실패해도 화면에선 이미 지운 채로 둔다 - 다음 진입 시 서버 목록으로 다시 맞춰짐 */
    });
  };

  const handleFillHistoryClick = async (item: FillHistoryItem) => {
    setFillError("");
    const error = await downloadFilledDocument(item.attachmentId, item.fileName);
    if (error) setFillError(error);
  };

  const handleLogout = () => {
    clearSession();
    navigate("/login");
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
              {profile ? [profile.profile_type, profile.region].filter(Boolean).join(" · ") || "정보 없음" : "예비창업자 · 마포구"}
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
              onDelete={handleRemoveInterest}
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
              <DeleteButton onClick={() => removeById(setFillHistory)(item.id)} />
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
              <DeleteButton onClick={() => removeById(setApplyHistory)(item.id)} />
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

      {/* 8. 하단 네비게이션 ("마이페이지" 탭 활성) */}
      <BottomNav active="my" />
    </div>
  );
}

export default MyPage;
