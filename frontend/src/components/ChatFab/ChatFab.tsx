import { useNavigate } from "react-router-dom";
import styles from "./ChatFab.module.css";
import fabIcon from "../../assets/8_white.png";

/**
 * 우측 고정 챗봇 상담 FAB (공통 컴포넌트).
 *
 * BottomNav처럼 전역 자동삽입이 아니라 필요한 화면마다 직접 `<ChatFab />`을 배치한다
 * (2026-09-13, 사용자 확인 — 화면끼리 서로 영향 안 주고 안전함). 클릭 시 항상
 * /support/chat(고객센터 챗봇)으로 이동. 원본은 pages/support/CustomerSupport.tsx.
 *
 * variant로 화면 상황에 맞는 위치를 고른다:
 *  - "default": 하단탭바/하단 CTA가 없는 화면 (right:16px, bottom:24px)
 *  - "withBottomNav": BottomNav(74px)가 있는 화면 — 탭바 위로 16px 띄움 (bottom:90px)
 *  - "top": 하단에 다른 CTA 버튼이 있는 화면 — 겹치지 않게 상단 배치 (top:60px)
 */
type ChatFabVariant = "default" | "withBottomNav" | "top";

interface ChatFabProps {
  variant?: ChatFabVariant;
  style?: React.CSSProperties; // 화면별 미세조정용 (인라인이라 variant보다 우선 적용됨)
}

const VARIANT_CLASS: Record<ChatFabVariant, string> = {
  default: "",
  withBottomNav: styles.withBottomNav,
  top: styles.top,
};

function ChatFab({ variant = "default", style }: ChatFabProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/support/chat");
  };

  return (
    <button
      type="button"
      className={`${styles.fab} ${VARIANT_CLASS[variant]}`}
      style={style}
      onClick={handleClick}
      aria-label="챗봇 상담 시작하기"
    >
      <img className={styles.fabImg} src={fabIcon} alt="" />
    </button>
  );
}

export default ChatFab;
export type { ChatFabVariant };
