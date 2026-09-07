import { useEffect } from "react";
import styles from "./termsModal.module.css";

interface TermsModalProps {
  // 약관 종류에 따라 제목/본문만 바꿔서 재사용한다.
  title: string;
  body: string;
  onClose: () => void;
}

// 약관 보기 팝업. 내용/페이지가 아직 없어 자리만 잡아두는 용도 —
// 실제 문구는 이 컴포넌트를 쓰는 쪽(예: Signup)에서 props로 넣는다.
// X 버튼 · 배경 클릭 · Esc 로 닫힌다. 백엔드 연동 없음.
function TermsModal({ title, body, onClose }: TermsModalProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);

    // 팝업 떠 있는 동안 뒤 화면 스크롤 잠금
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="닫기"
            autoFocus
          >
            ✕
          </button>
        </div>
        <p className={styles.body}>{body}</p>
      </div>
    </div>
  );
}

export default TermsModal;
