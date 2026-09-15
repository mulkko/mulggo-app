import { Fragment, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/matchingDetail.module.css";
import type { AnnouncementDetail } from "./matchingDetailData";
import { authHeaders } from "../../auth/session";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";
import Toast from "../../components/Toast/Toast";
import { useToast } from "../../components/Toast/useToast";
import BackButton from "../../components/BackButton/BackButton";

/**
 * 공고 상세(지원사업 상세) 화면.
 *
 * 공고 리스트(`/matching`)에서 카드를 누르면 `/matching/:id`로 들어온다.
 * URL의 id로 GET /api/matching/:id를 호출해 렌더한다 (id = announcements.announcement_id).
 *
 * [2026-09-13, 사용자 확인] 하단 네비게이션(BottomNav, active="matching") 추가함
 * (이전엔 상단에 뒤로가기 헤더만 있는 구조였음).
 *
 * 실제 동작으로 만든 것: 뒤로가기, 북마크(저장) 토글, 지원 여부 토글.
 * TODO로만 남긴 것: "채우기"(16-1 서류 미리보기 화면 예정). "공고 이동하기"는 구현 완료(detail.homepageUrl).
 * hashtags는 기업마당(bizinfo) 공고만 값이 있음(announcements_raw_bizinfo.hashtags,
 * K-Startup 원본엔 해당 필드 자체가 없음) - 2026-09-10 연동. aiComment는 백엔드가
 * 아직 자리만 채운 값(안내 문구)을 준다 - 사용자 프로필 연결(개인화)은 별도 작업.
 */

/**
 * 사업개요 4개 항목 아이콘. matchingDetailData의 overview 순서와 1:1로 매칭된다:
 * 0) 소관기관·수행기관(건물)  1) 지원 대상(사람)  2) 신청 방법(문서)  3) 문의처(전화)
 */
const OVERVIEW_ICONS = [
  <>
    <path d="M3 21V8l9-5 9 5v13" />
    <path d="M9 21v-6h6v6" />
  </>,
  <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" />
  </>,
  <>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="M3 9h18" />
  </>,
  <>
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.5 2.1L8 9.7a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2Z" />
  </>,
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function MatchingDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const location = useLocation();

  const [detail, setDetail] = useState<AnnouncementDetail | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [applied, setApplied] = useState(false);
  const [contentExpanded, setContentExpanded] = useState(false);
  const [noticeFileOpen, setNoticeFileOpen] = useState(false);
  const noticeFileExt = detail?.noticeFileName?.toLowerCase().split(".").pop();
  const isViewableNoticeFile = noticeFileExt === "pdf" || noticeFileExt === "hwpx";
  const { toastMessage, showToast } = useToast();

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE_URL}/api/matching/${id}`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((body: { success: boolean; data?: AnnouncementDetail }) => {
        setDetail(body.success ? body.data : undefined);
        setSaved(body.success ? Boolean(body.data?.bookmarked) : false);
        setApplied(body.success ? Boolean(body.data?.applied) : false);
      })
      .catch(() => setDetail(undefined))
      .finally(() => setLoading(false));
  }, [id]);

  const handleBack = () => {
    // [2026-09-10] navigate(-1)(브라우저 history 되돌리기)로 했었는데, 이 화면에
    // 직접 링크로 들어온 경우(공유 링크, 새로고침 등) history에 리스트가 없어서
    // 뒤로가기가 안 먹는 문제가 있었음. 대신 MatchingList가 카드 클릭 시 넘겨준
    // location.state.fromSearch로 필터 쿼리를 그대로 복원해 명시적으로 이동한다.
    // state가 없으면(직접 진입 등) 필터 없이 그냥 "/matching"으로.
    const fromSearch = (location.state as { fromSearch?: string } | null)?.fromSearch;
    navigate(fromSearch ? `/matching?${fromSearch}` : "/matching");
  };

  // [2026-09-15, 사용자 확인] 실패 시(비로그인 401 등) 조용히 원상복구만 하고 아무
  // 안내가 없어서, 로그인 세션이 없는 상태로 누르면 하트/체크가 잠깐 켜졌다가
  // 설명 없이 도로 꺼지는 것처럼 보이는 문제가 있었다(팀원 확인) - 실패 사유를
  // 토스트로 보여주도록 handleToggleSave/handleToggleApplied 둘 다 고친다.
  const showFailureToast = (res: Response) => {
    showToast(res.status === 401 ? "로그인이 필요합니다" : "처리에 실패했습니다. 다시 시도해주세요.");
  };

  const handleToggleSave = () => {
    // 낙관적으로 먼저 바꾸고, 실패하면(비로그인 401 등) 원래 상태로 되돌린다.
    const next = !saved;
    setSaved(next);
    fetch(`${API_BASE_URL}/api/matching/${id}/bookmark`, {
      method: next ? "POST" : "DELETE",
      headers: authHeaders(),
    }).then((res) => {
      if (!res.ok) {
        setSaved(!next);
        showFailureToast(res);
        return;
      }
      showToast(next ? "선택하신 공고가 찜하기 되었습니다" : "찜하기가 취소되었습니다");
    }).catch(() => {
      setSaved(!next);
      showToast("서버에 연결할 수 없습니다.");
    });
  };

  const handleToggleApplied = () => {
    // 낙관적으로 먼저 바꾸고, 실패하면(비로그인 401 등) 원래 상태로 되돌린다 (handleToggleSave와 동일 패턴).
    const next = !applied;
    setApplied(next);
    fetch(`${API_BASE_URL}/api/matching/${id}/apply`, {
      method: next ? "POST" : "DELETE",
      headers: authHeaders(),
    }).then((res) => {
      if (!res.ok) {
        setApplied(!next);
        showFailureToast(res);
        return;
      }
      showToast(next ? "지원한 공고로 표시되었습니다" : "지원 표시가 취소되었습니다");
    }).catch(() => {
      setApplied(!next);
      showToast("서버에 연결할 수 없습니다.");
    });
  };

  const handleFill = (doc: { fileName: string; attachmentId: number }) => {
    navigate(`/matching/${id}/doc-preview`, {
      state: { fileName: doc.fileName, attachmentId: doc.attachmentId },
    });
  };

  const handleGoHomepage = () => {
    if (detail?.homepageUrl) {
      window.open(detail.homepageUrl, "_blank", "noopener,noreferrer");
    }
  };

  if (loading) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <p className={styles.notFoundText}>불러오는 중...</p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <BackButton onClick={handleBack} />
            <span className={styles.headerTitle}>지원사업 상세</span>
          </div>
        </header>
        <div className={styles.notFound}>
          <p className={styles.notFoundText}>공고 정보를 찾을 수 없어요.</p>
          <button type="button" className={styles.notFoundLink} onClick={handleBack}>
            매칭 리스트로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 뒤로가기 + 타이틀 + 북마크(저장) 토글 */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <BackButton onClick={handleBack} />
          <span className={styles.headerTitle}>지원사업 상세</span>
        </div>
        <button
          type="button"
          className={styles.bookmarkButton}
          onClick={handleToggleSave}
          aria-pressed={saved}
          aria-label={saved ? "저장 해제" : "저장"}
        >
          <svg
            className={saved ? styles.bookmarkIconSaved : styles.bookmarkIcon}
            viewBox="0 0 24 24"
            strokeWidth="1.7"
            aria-hidden="true"
          >
            <path d="M6 3h12v18l-6-4.5L6 21Z" />
          </svg>
        </button>
      </header>

      <div className={styles.scrollArea}>
        {/* 접수기간 + D-day */}
        <div className={styles.metaRow}>
          <span className={styles.period}>{detail.period}</span>
          <span className={styles.ddayBadge}>{detail.dday}</span>
        </div>

        {/* 제목 */}
        <h1 className={styles.title}>{detail.title}</h1>

        {/* 해시태그 한 줄 */}
        <p className={styles.hashtags}>{detail.hashtags}</p>

        {/* 사업개요 카드 */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>사업 개요</h2>
          {detail.overview.map((item, index) => (
            <Fragment key={item.label}>
              {index > 0 && <div className={styles.divider} />}
              <div className={styles.overviewItem}>
                <div className={styles.overviewHead}>
                  <svg
                    className={styles.overviewIcon}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--color-overview-icon)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    {OVERVIEW_ICONS[index]}
                  </svg>
                  <span className={styles.overviewLabel}>{item.label}</span>
                </div>
                <span className={styles.overviewValue}>{item.value}</span>
              </div>
            </Fragment>
          ))}
        </section>

        {/* 공고 내용 카드 - 내용이 길면 약 6줄 높이로 접어두고, 그라데이션 + 버튼으로 펼침.
            [2026-09-10] 실제 줄 수를 재는 대신 근사 높이(132px)로 자름 - 사용자 결정(B안):
            내용이 132px보다 짧아도 버튼은 항상 보임(오버플로 여부를 JS로 안 재서 단순화). */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>공고 내용</h2>
          {/* [2026-09-15] PDF/HWPX는 서버가 원문 그대로 보여줄 수 있어서(PDF는 브라우저 내장
              뷰어, HWPX는 서버 변환 HTML) 요약 텍스트(content) 대신 iframe을 바로 띄운다.
              HWP(구버전)는 LibreOffice로 변환해보니 텍스트가 깨져서 뷰어를 못 만들었고,
              K-Startup은 원본 첨부 자체가 없다 - 이 둘은 기존 방식(요약 텍스트 + 다운로드용
              토글 버튼) 그대로 유지. */}
          {isViewableNoticeFile ? (
            <iframe
              src={`${API_BASE_URL}/api/matching/${id}/notice-file#toolbar=0&navpanes=0`}
              title="원본 공고문"
              style={{ width: "100%", height: 600, border: "none" }}
            />
          ) : (
            <>
              <div className={`${styles.contentWrap} ${contentExpanded ? "" : styles.contentCollapsed}`}>
                <p className={styles.contentBody}>{detail.content}</p>
                {!contentExpanded && <div className={styles.contentFade} aria-hidden="true" />}
              </div>
              <button
                type="button"
                className={styles.expandButton}
                onClick={() => setContentExpanded((prev) => !prev)}
              >
                {contentExpanded ? "접기" : "펼쳐보기"}
              </button>
              {detail.noticeFileName && (
                <>
                  <button
                    type="button"
                    className={styles.expandButton}
                    onClick={() => setNoticeFileOpen((prev) => !prev)}
                  >
                    {noticeFileOpen ? "원본 공고문 닫기" : "원본 공고문 보기"}
                  </button>
                  {noticeFileOpen && (
                    <iframe
                      src={`${API_BASE_URL}/api/matching/${id}/notice-file#toolbar=0&navpanes=0`}
                      title="원본 공고문"
                      style={{ width: "100%", height: 600, border: "none", marginTop: 10 }}
                    />
                  )}
                </>
              )}
            </>
          )}
        </section>

        {/* 서류 자동채움 안내 배너 */}
        <div className={styles.autofillBanner}>
          <span className={styles.autofillIcon} aria-hidden="true">✦</span>
          <span className={styles.autofillText}>서류 채우기를 누르면 저희가 채워드려요</span>
        </div>

        {/* 신청서류 카드 */}
        <section className={styles.docsCard}>
          <h2 className={styles.cardTitle}>신청서류</h2>
          {detail.docs.map((doc) => (
            <div key={doc.fileName} className={styles.docRow}>
              <span className={styles.docName}>{doc.fileName}</span>
              <div className={styles.docActions}>
                <a
                  href={doc.downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.fillButton}
                >
                  <span className={styles.fillButtonText}>원본 다운로드</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M9 6l6 6-6 6" />
                  </svg>
                </a>
                {doc.fillable && (
                  <button
                    type="button"
                    className={styles.fillButton}
                    onClick={() => handleFill(doc)}
                  >
                    <span className={styles.fillButtonText}>채우기</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </section>

        {/* 하단 CTA: 지원 여부 토글 + 원 공고 홈페이지 이동 */}
        <div className={styles.ctaRow}>
          <button
            type="button"
            className={`${styles.applyToggle} ${applied ? styles.applyToggleOn : styles.applyToggleOff}`}
            onClick={handleToggleApplied}
            aria-pressed={applied}
          >
            {applied ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12l5 5 9-11" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
                <rect x="4" y="4" width="16" height="16" rx="4" />
              </svg>
            )}
            <span className={styles.applyToggleText}>{applied ? "지원함" : "지원했어요"}</span>
          </button>
          <button
            type="button"
            className={styles.homeButton}
            onClick={handleGoHomepage}
            disabled={!detail.homepageUrl}
          >
            <span className={styles.homeButtonText}>공고 이동하기</span>
          </button>
        </div>
      </div>

      <Toast message={toastMessage} />

      <BottomNav active="matching" />
      <ChatFab variant="withBottomNav" />
    </div>
  );
}

export default MatchingDetail;
