import { Fragment, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/matchingDetail.module.css";
import { getAnnouncementDetail } from "./matchingDetailData";

/**
 * 공고 상세(지원사업 상세) 화면.
 *
 * 공고 리스트(`/matching`)에서 카드를 누르면 `/matching/:id`로 들어온다.
 * URL의 id로 matchingDetailData의 더미 레코드를 찾아 렌더한다.
 *
 * 이 화면에는 하단 네비게이션(BottomNav)이 없다 — 상단에 뒤로가기 헤더만 있는 구조.
 *
 * 실제 동작으로 만든 것: 뒤로가기, 북마크(저장) 토글, 지원 여부 토글.
 * TODO로만 남긴 것: "채우기"(16-1 서류 미리보기 화면 예정), "원 공고 홈페이지로 이동"(외부 URL 미정).
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

function MatchingDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const detail = getAnnouncementDetail(id);

  const [saved, setSaved] = useState(false);
  const [applied, setApplied] = useState(false);

  const handleBack = () => {
    navigate("/matching");
  };

  const handleToggleSave = () => {
    setSaved((prev) => !prev);
  };

  const handleToggleApplied = () => {
    setApplied((prev) => !prev);
  };

  const handleFill = () => {
    // TODO: 16-1 서류 미리보기 화면으로 이동 (별도 작업 예정)
  };

  const handleGoHomepage = () => {
    // TODO: 원 공고 홈페이지(외부 URL)로 이동 — detail.homepageUrl 연결 예정
  };

  if (!detail) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <header className={styles.header}>
          <div className={styles.headerLeft}>
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

        {/* AI 코멘트 박스 */}
        <div className={styles.aiBox}>
          <span className={styles.aiTitle}>AI 코멘트</span>
          <p className={styles.aiBody}>{detail.aiComment}</p>
        </div>

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

        {/* 공고 내용 카드 */}
        <section className={styles.card}>
          <h2 className={styles.cardTitle}>공고 내용</h2>
          <p className={styles.contentBody}>{detail.content}</p>
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
              <button type="button" className={styles.fillButton} onClick={handleFill}>
                <span className={styles.fillButtonText}>채우기</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" />
                </svg>
              </button>
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
            <span className={styles.applyToggleText}>{applied ? "지원함" : "지원 시 체크"}</span>
          </button>
          <button type="button" className={styles.homeButton} onClick={handleGoHomepage}>
            <span className={styles.homeButtonText}>원 공고 홈페이지로 이동</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default MatchingDetail;
