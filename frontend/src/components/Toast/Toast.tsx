import styles from "./toast.module.css";

interface ToastProps {
  message: string | null;
}

/** 하단 토스트 메시지 (공용 컴포넌트). message가 없으면 아무것도 렌더링하지 않는다.
 * 상태/타이머 관리는 useToast() 훅에서 한다 - 이 컴포넌트는 표시만 담당. */
function Toast({ message }: ToastProps) {
  if (!message) return null;
  return (
    <div className={styles.toast} role="status">
      {message}
    </div>
  );
}

export default Toast;
