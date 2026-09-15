import styles from "./backButton.module.css";

interface BackButtonProps {
  onClick: () => void;
  /** 화면마다 헤더 레이아웃이 달라(로고/타이틀/우측 액션 유무) 버튼을 감싸는
   * 컨테이너의 flex 정렬은 각 화면이 그대로 맡는다 - 이 컴포넌트는 100% 동일했던
   * 버튼 자체(아이콘+동작)만 담당. 드물게 위치 보정이 필요하면 className으로 추가. */
  className?: string;
}

/** 뒤로가기 버튼(공용). 화면 10곳 넘게 완전히 동일한 SVG+버튼 마크업이 복붙돼
 * 있던 걸 통합했다(2026-09-15). */
function BackButton({ onClick, className }: BackButtonProps) {
  return (
    <button
      type="button"
      className={className ? `${styles.backButton} ${className}` : styles.backButton}
      onClick={onClick}
      aria-label="뒤로가기"
    >
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
    </button>
  );
}

export default BackButton;
