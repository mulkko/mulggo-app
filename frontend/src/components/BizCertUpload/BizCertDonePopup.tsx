import styles from "./bizCertDonePopup.module.css";
import bizDoneCharacter from "../../assets/2_hello.png";

interface BizCertDonePopupProps {
  // "지원사업 보러가기" 클릭 시 - 서버 저장 후 /matching 이동은 호출부(Onboarding.tsx)가 담당.
  onProceed: () => void;
  // 저장 요청 중이면 버튼을 비활성화하고 문구를 바꾼다.
  saving?: boolean;
  // 저장 실패 시 안내 문구 - 실패해도 이 팝업 자체는 유지하고 버튼을 다시 누를 수 있게 한다.
  error?: string;
}

/**
 * 사업자등록증 인식 완료 팝업 — 온보딩 step5 "사업자등록증 등록" 팝업(BizCertUpload 기반)에서
 * OCR 확인이 끝나면(fields 확정) 그 팝업을 대체해서 뜨는 별도 팝업.
 * 시나리오 보드 "회원가입 검증 상태.dc.html" 16번 "가입완료(사업자등록증 인식 완료)" 실측값.
 */
function BizCertDonePopup({ onProceed, saving = false, error }: BizCertDonePopupProps) {
  return (
    <div className={styles.overlay}>
      <div className={styles.card} role="dialog" aria-modal="true" aria-label="사업자등록증 인식 완료">
        <img src={bizDoneCharacter} alt="" className={styles.illustration} />
        <p className={styles.title}>김창업님, 물꼬가 트였어요!</p>
        <p className={styles.desc}>사업자 정보까지 준비됐어요. 이제 딱 맞는 지원사업을 찾아볼까요?</p>
        {error && <p className={styles.error}>{error}</p>}
        <button type="button" className={styles.proceedBtn} onClick={onProceed} disabled={saving}>
          {saving ? "이동 중..." : "지원사업 보러가기"}
        </button>
      </div>
    </div>
  );
}

export default BizCertDonePopup;
