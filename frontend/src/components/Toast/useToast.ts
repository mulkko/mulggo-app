import { useCallback, useRef, useState } from "react";

const TOAST_DURATION_MS = 1500;

/**
 * 하단 토스트 메시지 공용 훅.
 *
 * MatchingDetail.tsx/MyPage.tsx가 각자 `useState + setTimeout(1500ms)`를
 * 똑같이 복붙해서 쓰던 걸 하나로 합쳤다(2026-09-15). `showToast(text)` 한 번만
 * 호출하면 표시+자동소멸까지 알아서 되고, `toastMessage`를 <Toast /> 컴포넌트에
 * 그대로 넘기면 된다.
 */
export function useToast() {
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((text: string) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToastMessage(text);
    timerRef.current = setTimeout(() => setToastMessage(null), TOAST_DURATION_MS);
  }, []);

  return { toastMessage, showToast };
}
