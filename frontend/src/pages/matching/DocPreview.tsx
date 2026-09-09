import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/docPreview.module.css";
import { getAnnouncementDetail } from "./matchingDetailData";

/**
 * 서류 미리보기 화면 (16-1).
 *
 * 공고 상세(MatchingDetail.tsx)의 신청서류 카드에서 "채우기"를 누르면
 * `/matching/:id/doc-preview`로 들어온다. 파일명/attachmentId는 navigate
 * state로 넘어오고, state 없이 URL로 직접 접근한 경우 더미데이터로 fallback한다.
 *
 * 하단 네비게이션(BottomNav) 없음 — 뒤로가기 헤더만 있는 구조(뒤로가기 → /matching/:id).
 *
 * 실제 동작으로 만든 것: 뒤로가기, "나의 정보로 채우기"
 *   → GET /api/matching/attachments/:id/fill 호출해서 실제로 채운 hwpx를 새 탭으로 다운로드.
 *   [2026-09-09, 임시] 로그인 세션이 없어서 백엔드가 DB에 등록된 사업자등록증 1건(임시)으로
 *   채운다 - 로그인 붙으면 그 사용자 정보로 자동 전환됨(백엔드 쪽 작업).
 * TODO로만 남긴 것: 카카오톡 공유.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function DocPreview() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  const state = location.state as { fileName?: string; attachmentId?: number } | null;
  const fileName = state?.fileName ?? getAnnouncementDetail(id)?.docs[0]?.fileName ?? "신청 서류";
  const attachmentId = state?.attachmentId;

  // 다운로드 모달 open 여부 — 이 화면 안에서만 쓰는 로컬 UI 상태
  const [downloadOpen, setDownloadOpen] = useState(false);

  const handleBack = () => {
    navigate(`/matching/${id}`);
  };

  const handleFill = () => {
    if (attachmentId) {
      window.open(`${API_BASE_URL}/api/matching/attachments/${attachmentId}/fill`, "_blank");
      return;
    }
    // attachmentId 없이 들어온 경우(더미데이터 fallback) - 실제 실행할 대상이 없어 모달만 보여준다.
    setDownloadOpen(true);
  };

  const handleCloseModal = () => {
    setDownloadOpen(false);
  };

  const handleLocalSave = () => {
    // TODO: 생성된 문서를 로컬 저장소로 다운로드 — 지금은 모달만 닫는다
    setDownloadOpen(false);
  };

  const handleKakaoShare = () => {
    // TODO: 카카오톡 공유 SDK 연동 — 지금은 모달만 닫는다
    setDownloadOpen(false);
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 뒤로가기 + 파일명 */}
      <header className={styles.header}>
        <button
          type="button"
          className={styles.backButton}
          onClick={handleBack}
          aria-label="뒤로가기"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.headerTitle}>{fileName}</span>
      </header>

      <main className={styles.body}>
        <div className={styles.iconCircle}>
          <svg
            className={styles.docIcon}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
            <path d="M14 3v5h5" />
            <path d="M9 13h6" />
            <path d="M9 17h6" />
          </svg>
        </div>
        <h1 className={styles.docTitle}>{fileName}</h1>
        <p className={styles.docDesc}>
          아직 만들지 않았어요. 회원님의 사업자 프로필에서
          상호명·대표자명·사업자등록번호·사업장 주소·연락처 등으로 채워 문서를 만들어드려요.
        </p>
      </main>

      <div className={styles.ctaBar}>
        <button type="button" className={styles.fillButton} onClick={handleFill}>
          나의 정보로 채우기
        </button>
      </div>

      {downloadOpen && (
        <div className={styles.overlay} onClick={handleCloseModal}>
          <div
            className={styles.modalCard}
            role="dialog"
            aria-modal="true"
            aria-label="서류 다운로드"
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.modalHead}>
              <p className={styles.modalTitle}>서류가 준비됐어요</p>
              <p className={styles.modalSub}>{fileName}</p>
            </div>
            <div className={styles.modalButtons}>
              <button
                type="button"
                className={styles.localSaveButton}
                onClick={handleLocalSave}
              >
                <svg
                  className={styles.modalIcon}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 3v12" />
                  <path d="M7 11l5 5 5-5" />
                  <path d="M5 20h14" />
                </svg>
                <span className={styles.modalButtonText}>{"로컬 저장소에\n저장하기"}</span>
              </button>
              <button
                type="button"
                className={styles.kakaoButton}
                onClick={handleKakaoShare}
              >
                <svg
                  className={styles.modalIcon}
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M12 3.5C6.75 3.5 2.5 6.9 2.5 11.1c0 2.7 1.79 5.06 4.5 6.42-.2.72-.72 2.62-.83 3.03-.13.5.19.5.39.36.16-.1 2.55-1.73 3.58-2.44.44.06.9.09 1.36.09 5.25 0 9.5-3.4 9.5-7.6S17.25 3.5 12 3.5z" />
                </svg>
                <span className={styles.modalButtonText}>{"카카오톡\n공유하기"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DocPreview;
