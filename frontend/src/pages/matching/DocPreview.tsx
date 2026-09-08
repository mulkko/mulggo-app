import { useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/docPreview.module.css";
import { getAnnouncementDetail } from "./matchingDetailData";

/**
 * 서류 미리보기 화면 (16-1).
 *
 * 공고 상세(MatchingDetail.tsx)의 신청서류 카드에서 "채우기"를 누르면
 * `/matching/:id/doc-preview`로 들어온다. 파일명은 navigate state(`fileName`)로 넘어오고,
 * state 없이 URL로 직접 접근한 경우 id로 더미데이터의 첫 번째 서류명을 fallback으로 쓴다.
 *
 * 하단 네비게이션(BottomNav) 없음 — 뒤로가기 헤더만 있는 구조(뒤로가기 → /matching/:id).
 *
 * 실제 동작으로 만든 것: 뒤로가기, "나의 정보로 채우기" → 다운로드 모달 열기/닫기(로컬 state).
 * TODO로만 남긴 것: 실제 문서 생성, 로컬 저장(다운로드), 카카오톡 공유.
 */

function DocPreview() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  const stateFileName = (location.state as { fileName?: string } | null)?.fileName;
  const fileName =
    stateFileName ?? getAnnouncementDetail(id)?.docs[0]?.fileName ?? "신청 서류";

  // 다운로드 모달 open 여부 — 이 화면 안에서만 쓰는 로컬 UI 상태
  const [downloadOpen, setDownloadOpen] = useState(false);

  const handleBack = () => {
    navigate(`/matching/${id}`);
  };

  const handleFill = () => {
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
