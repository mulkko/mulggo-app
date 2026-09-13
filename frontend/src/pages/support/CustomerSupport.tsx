import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/customerSupport.module.css";
import chatCardAvatarIcon from "../../assets/9_mint.svg";
import BottomNav from "../../components/BottomNav/BottomNav";
import ChatFab from "../../components/ChatFab/ChatFab";

/**
 * 1:1 문의 화면 (19번, /support). 하위 화면: 19-1번 고객센터 챗봇(/support/chat, CustomerSupportChat.tsx).
 *
 * TODO(2026-09-11 기준): 문의 제출/조회 백엔드 미구현 — 프론트만 우선 구현. 백엔드
 * 준비되면 연동 필요(제출 API, "나의 문의 내역" 조회 API 둘 다 없음 확인).
 * 지금은 제출 시 프론트 유효성 검사만 하고 실제 저장 없이 완료 UI만 보여준다.
 */

type InquiryType = "매칭 오류" | "기능 제안" | "버그 신고" | "기타";

const INQUIRY_TYPES: InquiryType[] = ["매칭 오류", "기능 제안", "버그 신고", "기타"];

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function BackIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M16 5l-8 7 8 7" />
    </svg>
  );
}

function ChatArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function CustomerSupport() {
  const navigate = useNavigate();
  const [inquiryType, setInquiryType] = useState<InquiryType>(INQUIRY_TYPES[0]);
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleBack = () => {
    navigate(-1);
  };

  const handleChatCardClick = () => {
    navigate("/support/chat");
  };

  const messageError = touched && message.trim().length === 0 ? "건의사항을 입력해주세요." : "";
  const emailError =
    touched && email.trim().length > 0 && !EMAIL_PATTERN.test(email.trim())
      ? "이메일 형식을 확인해주세요."
      : touched && email.trim().length === 0
        ? "답변 받을 이메일을 입력해주세요."
        : "";

  const isValid = message.trim().length > 0 && EMAIL_PATTERN.test(email.trim());

  const handleSubmit = () => {
    setTouched(true);
    if (!isValid) return;
    setSubmitted(true);
    setInquiryType(INQUIRY_TYPES[0]);
    setMessage("");
    setEmail("");
    setTouched(false);
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <BackIcon />
        </button>
        <span className={styles.headerTitle}>1:1 문의</span>
      </header>

      <main className={styles.content}>
        <div className={styles.intro}>
          <h1 className={styles.introTitle}>무엇을 도와드릴까요?</h1>
          <p className={styles.introSub}>
            버그, 오류, 개선 제안 등 어떤 의견이든 편하게 남겨주세요. 빠르게 확인하고 답변드릴게요.
          </p>
        </div>

        <button type="button" className={styles.chatCard} onClick={handleChatCardClick}>
          <span className={styles.chatCardAvatar}>
            <img className={styles.chatCardAvatarImg} src={chatCardAvatarIcon} alt="" />
          </span>
          <span className={styles.chatCardText}>
            <span className={styles.chatCardTitle}>챗봇에게 먼저 물어보기</span>
            <span className={styles.chatCardSub}>자주 묻는 질문은 챗봇이 바로 답해드려요</span>
          </span>
          <span className={styles.chatCardArrow}>
            <ChatArrowIcon />
          </span>
        </button>

        <div className={styles.field}>
          <span className={styles.label}>문의 유형</span>
          <div className={styles.typeRow} role="radiogroup" aria-label="문의 유형">
            {INQUIRY_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                role="radio"
                aria-checked={inquiryType === type}
                className={`${styles.typeChip} ${inquiryType === type ? styles.typeChipSelected : ""}`}
                onClick={() => setInquiryType(type)}
              >
                <span className={styles.typeChipDot} />
                {type}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="support-message">
            건의사항
          </label>
          <textarea
            id="support-message"
            className={`${styles.textarea} ${messageError ? styles.inputError : ""}`}
            placeholder="예: 상권분석 지도가 로딩되지 않아요..."
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          {messageError && <p className={styles.errorText}>{messageError}</p>}
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="support-email">
            답변 받을 이메일
          </label>
          <input
            id="support-email"
            className={`${styles.input} ${emailError ? styles.inputError : ""}`}
            type="email"
            placeholder="example@email.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {emailError && <p className={styles.errorText}>{emailError}</p>}
        </div>

        <button type="button" className={styles.submitButton} onClick={handleSubmit}>
          문의 접수하기
        </button>
        {submitted && <p className={styles.submittedText}>문의가 접수되었어요. 빠르게 확인하고 답변드릴게요.</p>}

        <div className={styles.divider} />

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>나의 문의 내역</h2>
          <p className={styles.emptyText}>아직 접수한 문의가 없어요</p>
        </section>
      </main>

      <ChatFab variant="withBottomNav" />

      <BottomNav active="my" />
    </div>
  );
}

export default CustomerSupport;
