import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import styles from "../../styles/onboarding.module.css";
import BizCertUpload, {
  type BizCertUploadHandle,
} from "../../components/BizCertUpload/BizCertUpload";

/**
 * 온보딩 화면 (`/onboarding`).
 *
 * 회원가입 완료 직후 진입한다. step(0~3) 로컬 state 하나로
 * 본문(마스코트 + 카피)과 하단 페이지 인디케이터 / CTA 전환을 모두 처리한다.
 * 백엔드 / URL 파라미터 연동 없음.
 *
 * - step 0: 가입 완료 인사
 * - step 1: 사업 구체화 소개
 * - step 2: 맞춤 분석 소개
 * - step 3: 시작 방식 선택 (카드 2개) — 하단 영역(인디케이터 + CTA) 없음
 *
 * 스펙 출처: 프로토타입 "is.onboard". 하단 네비게이션(BottomNav) 없음.
 * 값(색상/radius/shadow)은 webTokens.css 토큰만 사용한다.
 *
 * [2026-09-10] step3 "바로 지원사업 매칭을 받아보고 싶어요" 카드 → 사업자등록증
 * 첨부 팝업(BizCertUpload, 원래 Signup.tsx에 있던 컴포넌트를 여기로 옮겨옴 - 사용자
 * 확인). Signup.tsx가 가입 성공 시 navigate state로 user_id를 넘겨주는데(로그인
 * 세션은 가입 직후엔 아직 없어서), dev_links.html의 "회원가입_완료"처럼 온보딩에
 * 직접 URL로 들어와 state가 없는 경우엔 FALLBACK_USER_ID(27, MyPage.tsx/
 * ProfileEdit.tsx와 동일)로 대신 채워서 팝업 자체는 항상 테스트 가능하게 한다.
 * 팝업 흐름: 드롭존(취소만 노출) → OCR 확인(BizCertUpload 자체 오버레이) → 확인
 * 완료 요약 상태로 전환되면 그때 "진행하기"가 나타남 → POST /api/mypage/biz-cert
 * 저장 후 /matching 이동.
 */

type Step = 0 | 1 | 2 | 3;

type StepContent = {
  badge?: string;
  title: string; // <br> 포함 — 줄바꿈 위치가 디자인 스펙
  desc?: string;
};

/** step 0~2 본문 카피 — 프로토타입 값 그대로. 이름은 더미데이터 일관성 위해 "김창업". */
const STEP_CONTENT: Record<0 | 1 | 2, StepContent> = {
  0: {
    title: "김창업 님,<br>가입이 완료되었습니다",
  },
  1: {
    badge: "STEP 1 · 사업 구체화",
    title: "막연한 생각도<br>질문에 답하면 사업이 돼요",
    desc: "물꼬 AI가 아이템·문제·해결방식을 차례로 물어보고 PSST 형식으로 정리해 드려요.",
  },
  2: {
    badge: "STEP 2 · 맞춤 분석",
    title: "업종코드를 찾아<br>상권·기술창업 분석까지",
    desc: "정리된 내용으로 업종코드를 판정해 상권형 또는 기술창업형 리포트로 이어드려요.",
  },
};

const TOTAL_STEPS = 4;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/** 마스코트 원 — 모든 step 공통. 안쪽은 임시 placeholder 도형. */
function Mascot() {
  return (
    <div className={styles.mascot} aria-hidden="true">
      <div className={styles.mascotInner} />
    </div>
  );
}

function Onboarding() {
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState<Step>(0);

  // dev_links.html의 "회원가입_완료"가 /onboarding으로 직접 연결돼 있어서(실제 회원가입을
  // 안 거친 진입), 그 경우 location.state가 비어 userId가 없다 - 폴백값으로 채워서
  // 팝업 자체는 항상 테스트 가능하게 한다(MyPage.tsx/ProfileEdit.tsx의 FALLBACK_USER_ID와 동일 이유).
  const FALLBACK_USER_ID = 27;
  const userId = (location.state as { userId?: number } | null)?.userId ?? FALLBACK_USER_ID;

  // 사업자등록증 첨부 팝업 상태
  const bizCertRef = useRef<BizCertUploadHandle>(null);
  const [bizCertOpen, setBizCertOpen] = useState(false);
  const [bizCertFileName, setBizCertFileName] = useState<string | null>(null);
  const [bizCertRunning, setBizCertRunning] = useState(false);
  const [bizCertFields, setBizCertFields] = useState<Record<string, string> | null>(null);
  const [bizCertFile, setBizCertFile] = useState<File | null>(null);
  const [bizCertSaving, setBizCertSaving] = useState(false);
  const [bizCertError, setBizCertError] = useState("");

  const handleBack = () => {
    // step 0에서만 노출 — 회원가입 화면으로 복귀 (이미 있는 라우트)
    navigate("/signup");
  };

  const handleSkip = () => {
    navigate("/home");
  };

  const handleNext = () => {
    setStep((prev) => (prev < 3 ? ((prev + 1) as Step) : prev));
  };

  const handleIdeaCard = () => {
    // [2026-09-10] 진단 진입점은 /idea/choice(빠른매칭 vs 정밀구체화) → 이후 /diagnosis/select로 이어짐.
    navigate("/idea/choice");
  };

  const handleMatchingCard = () => {
    setBizCertOpen(true);
  };

  const closeBizCertPopup = () => {
    setBizCertOpen(false);
    setBizCertFileName(null);
    setBizCertRunning(false);
    setBizCertFields(null);
    setBizCertFile(null);
    setBizCertError("");
  };

  const handleBizCertFileSelected = (file: File) => {
    setBizCertFileName(file.name);
  };

  // 오른쪽 버튼의 "실행하기" 역할 — 파일 선택 후, 그제서야 OCR을 시작한다
  // (BizCertUpload가 deferStart라 선택 즉시 자동 시작 안 함, ref로 수동 트리거).
  const handleBizCertRun = () => {
    setBizCertRunning(true);
    bizCertRef.current?.start();
  };

  // BizCertUpload가 실패 후 "selected" 단계로 되돌아갈 때(handleBizCertError가
  // ref.reset()을 호출한 경우) 호출됨 - 파일명은 그대로 유지되므로(BizCertUpload가
  // 파일을 지우지 않음) 여기선 "처리 중..." 상태만 풀어서 바로 재실행할 수 있게 한다.
  const handleBizCertReset = () => {
    setBizCertRunning(false);
  };

  // [2026-09-10] OCR 실패 시 BizCertUpload 내부 error 화면(팝업 안에 또 다른 화면이
  // 겹쳐 보임) 대신, 경고창 하나로 알리고 바로 파일 선택 가능한 상태로 되돌린다.
  const handleBizCertError = (message: string) => {
    alert(`${message}\n다시 실행해주세요.`);
    bizCertRef.current?.reset();
  };

  const handleBizCertConfirm = (fields: Record<string, string>, file: File) => {
    setBizCertFields(fields);
    setBizCertFile(file);
  };

  const handleBizCertProceed = async () => {
    if (!bizCertFields || !bizCertFile || !userId) return;
    setBizCertSaving(true);
    setBizCertError("");
    try {
      const formData = new FormData();
      formData.append("file", bizCertFile);
      formData.append("biz_cert_data", JSON.stringify(bizCertFields));
      const res = await fetch(`${API_BASE_URL}/api/mypage/biz-cert?user_id=${userId}`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        setBizCertError("저장에 실패했어요. 다시 시도해주세요.");
        return;
      }
      navigate("/matching");
    } catch {
      setBizCertError("서버에 연결할 수 없어요.");
    } finally {
      setBizCertSaving(false);
    }
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 상단바: 뒤로가기(step 0만) + 건너뛰기(step 0~2) */}
      <header className={styles.topbar}>
        {step === 0 ? (
          <button
            type="button"
            className={styles.backButton}
            onClick={handleBack}
            aria-label="뒤로가기"
          >
            ←
          </button>
        ) : (
          <span />
        )}
        {step !== 3 && (
          <button type="button" className={styles.skipButton} onClick={handleSkip}>
            건너뛰기
          </button>
        )}
      </header>

      {/* 중앙 콘텐츠 */}
      <main className={styles.content}>
        {step === 3 ? (
          <>
            <Mascot />
            <div className={styles.startHeading}>
              <h1 className={styles.startTitle}>
                이제 물꼬를 시작해볼
                <br />
                준비가 되셔나요?
              </h1>
              <p className={styles.startSubtitle}>무엇부터 해보고 싶은지 알려주세요.</p>
            </div>
            <div className={styles.cardList}>
              <button type="button" className={styles.choiceCard} onClick={handleIdeaCard}>
                <span className={styles.choiceCardTitle}>사업 아이디어를 구상하고 싶어요</span>
                <span className={styles.choiceCardDesc}>
                  짧은 질문 혹은 정밀 질문에 답하며 사업을 구체화해요
                </span>
              </button>
              <button type="button" className={styles.choiceCard} onClick={handleMatchingCard}>
                <span className={styles.choiceCardTitle}>바로 지원사업 매칭을 받아보고 싶어요</span>
                <span className={styles.choiceCardDesc}>
                  이미 사업 정보가 있다면 바로 지원사업을 확인해요
                </span>
              </button>
            </div>
          </>
        ) : (
          <>
            <Mascot />
            {STEP_CONTENT[step].badge && (
              <span className={styles.badge}>{STEP_CONTENT[step].badge}</span>
            )}
            <h1
              className={styles.title}
              dangerouslySetInnerHTML={{ __html: STEP_CONTENT[step].title }}
            />
            {STEP_CONTENT[step].desc && (
              <p className={styles.desc}>{STEP_CONTENT[step].desc}</p>
            )}
          </>
        )}
      </main>

      {/* 하단 영역: step 0~2만 */}
      {step !== 3 && (
        <footer className={styles.bottom}>
          <div className={styles.dots} role="presentation">
            {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
              <span
                key={i}
                className={`${styles.dot} ${i === step ? styles.dotActive : ""}`}
              />
            ))}
          </div>
          <button type="button" className={styles.cta} onClick={handleNext}>
            다음
          </button>
        </footer>
      )}

      {/* 사업자등록증 첨부 팝업 (step3 "바로 지원사업 매칭을 받아보고 싶어요") */}
      {bizCertOpen && (() => {
        // OCR이 실제로 도는 동안(uploading/review)은 BizCertUpload 자기 화면(전체 오버레이)이
        // 대신 보여야 하므로, 이 팝업 자체의 제목/설명/버튼은 잠깐 숨긴다 - 안 그러면
        // 두 오버레이가 겹쳐 보이는 "다중 팝업"처럼 보임.
        const ocrRunning = bizCertRunning && !bizCertFields;
        return (
          <div
            className={ocrRunning ? styles.bizPopupBare : styles.bizPopupOverlay}
            onClick={closeBizCertPopup}
          >
            <div
              className={ocrRunning ? styles.bizPopupBare : styles.bizPopupCard}
              role="dialog"
              aria-modal="true"
              aria-label="사업자등록증 첨부"
              onClick={(e) => e.stopPropagation()}
            >
              {!ocrRunning && (
                <>
                  <h2 className={styles.bizPopupTitle}>사업자등록증을 첨부해주세요</h2>
                  <p className={styles.bizPopupSub}>
                    등록하면 회원님의 사업 정보로 바로 지원사업 매칭을 시작할 수 있어요.
                  </p>
                </>
              )}

              {bizCertFields ? (
                <p className={styles.bizPopupDone}>사업자등록증 확인 완료 ✓</p>
              ) : (
                <BizCertUpload
                  ref={bizCertRef}
                  deferStart
                  onFileSelected={handleBizCertFileSelected}
                  onConfirm={handleBizCertConfirm}
                  onSkip={closeBizCertPopup}
                  onReset={handleBizCertReset}
                  onError={handleBizCertError}
                />
              )}

              {bizCertError && <p className={styles.bizPopupError}>{bizCertError}</p>}

              {!ocrRunning && (
                <div className={styles.bizPopupButtons}>
                  <button type="button" className={styles.bizPopupCancelBtn} onClick={closeBizCertPopup}>
                    취소
                  </button>
                  <button
                    type="button"
                    className={styles.bizPopupProceedBtn}
                    onClick={bizCertFields ? handleBizCertProceed : handleBizCertRun}
                    disabled={bizCertFields ? bizCertSaving : !bizCertFileName || bizCertRunning}
                  >
                    {bizCertFields
                      ? bizCertSaving
                        ? "저장 중..."
                        : "진행하기"
                      : bizCertRunning
                        ? "처리 중..."
                        : "실행하기"}
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export default Onboarding;
