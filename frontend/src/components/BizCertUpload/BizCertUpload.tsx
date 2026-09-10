import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import type { ChangeEvent } from "react";
import styles from "./bizCertUpload.module.css";

/** 법인/개인 필드 - 값 자체를 누르면 선택 팝업이 뜬다는 걸 알려주는 화살표. */
function Chevron() {
  return (
    <svg
      className={styles.chevron}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

// OCR 하이브리드 구조: 팀원 각자 자기 PC에서 localhost로 프론트를 띄우지만,
// OCR(무거운 모델)만은 GPU가 있는 고정 PC로 보낸다.
//   1) 브라우저에 저장해둔 주소가 있으면 그걸 우선 사용
//      (주소가 바뀌면 개발자 콘솔에서 localStorage.setItem("ocr_api_base_url", "http://새주소:8000") 로 갱신)
//   2) 없으면 GPU PC 고정 주소 사용
const OCR_SERVER_HOST = "192.168.0.160";

function resolveOcrApiBaseUrl(): string {
  const saved = localStorage.getItem("ocr_api_base_url");
  if (saved) return saved;
  return `http://${OCR_SERVER_HOST}:8000`;
}

const OCR_API_BASE_URL = resolveOcrApiBaseUrl();

const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];
const MAX_FILE_SIZE_MB = 10;

// 화면에 보여줄 필드 목록. key는 백엔드(_extracted_to_fields)가 내려주는 평탄화된 key와 동일해야 함.
const REVIEW_FIELDS: { key: string; label: string }[] = [
  { key: "company_name", label: "상호 / 법인명" },
  { key: "ceo_name", label: "대표자명" },
  { key: "biz_no", label: "사업자등록번호" },
  { key: "corp_no", label: "법인등록번호" },
  { key: "open_date", label: "개업연월일" },
  { key: "birth_date", label: "생년월일" },
  { key: "business_address", label: "사업장 소재지" },
  { key: "business_category", label: "업태" },
  { key: "business_item", label: "종목" },
];

// 법인/개인 구분에 따라 애초에 존재하지 않는 필드 (법인등록번호는 법인만, 생년월일은 개인만).
const NOT_APPLICABLE_WHEN: Record<string, string> = {
  corp_no: "개인",
  birth_date: "법인",
};

// DB(biz_registration_docs)가 NOT NULL로 요구하는 필드 — 확인 버튼 누르기 전에 채워져 있어야 함.
const REQUIRED_FIELDS = ["company_name", "ceo_name", "biz_no", "open_date", "business_address"];

// 업태/종목 - 표준 목록이 없는 자유 기재 항목이라 비어 있어도 경고(빨간 테두리) 없이
// "선택 사항"으로만 안내한다.
const OPTIONAL_FIELDS = new Set(["business_category", "business_item"]);

const ERROR_FALLBACK = "알 수 없는 오류가 발생했습니다.";

interface OcrResponse {
  ocr_success: boolean;
  extracted: Record<string, string> | null;
  error: string | null;
  error_type: string | null;
  error_label: string | null;
}

interface BizCertUploadProps {
  // 사용자가 결과를 확인/수정하고 "확인"을 눌렀을 때. 회원가입 제출 시 file은 그대로,
  // fields는 JSON으로 같이 보내면 백엔드가 재OCR 없이 이 값을 그대로 저장한다.
  onConfirm: (fields: Record<string, string>, file: File) => void;
  // "나중에 하기" — 사업자등록증 없이 진행 (선택 사항이라 항상 가능).
  onSkip: () => void;
  // [2026-09-10] true면 파일 선택해도 OCR을 바로 시작 안 하고 파일명만 보여주며
  // 대기한다 - 부모가 ref.start()로 수동 시작(Onboarding.tsx 팝업의 "실행하기"
  // 버튼용). 기본 false면 기존 동작(선택 즉시 자동 시작) 그대로 유지.
  deferStart?: boolean;
  // deferStart일 때, 파일이 선택돼서 "실행하기"를 누를 수 있게 됐음을 부모에게 알림.
  onFileSelected?: (file: File) => void;
  // [2026-09-10] OCR 실패 후 "다시 시도"를 누르면 내부적으로 idle로 돌아가는데(파일도
  // 지워짐), deferStart 쓰는 부모(Onboarding.tsx)의 바깥 버튼 상태(파일명/실행중 여부)도
  // 같이 리셋해야 팝업을 닫았다 열지 않고도 바로 재실행할 수 있어서 이 콜백으로 알려준다.
  onReset?: () => void;
  // [2026-09-10] OCR 실패한 순간 바로 알림 - 넘기면 부모가 자체 경고창(alert 등)으로
  // 대신 안내하고 ref.reset()으로 강제 복귀시키는 용도(Onboarding.tsx 팝업). 안 넘기면
  // (Signup.tsx/ProfileEdit.tsx처럼) 기존과 동일하게 내부 error 페이즈만 보여준다.
  onError?: (message: string) => void;
}

export interface BizCertUploadHandle {
  /** deferStart=true일 때 선택된 파일로 OCR 시작. 선택된 파일 없으면 아무 일도 안 함. */
  start: () => void;
  /** idle(파일 선택 전) 상태로 강제 복귀. onError와 함께 써서 내부 error 페이즈를 건너뛸 때 씀. */
  reset: () => void;
}

type Phase = "idle" | "selected" | "uploading" | "error" | "review";

function validateFile(file: File): string | null {
  const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return "jpg, png, pdf 파일만 업로드할 수 있어요.";
  }
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `파일 용량은 ${MAX_FILE_SIZE_MB}MB 이하만 가능해요.`;
  }
  return null;
}

const BizCertUpload = forwardRef<BizCertUploadHandle, BizCertUploadProps>(function BizCertUpload(
  { onConfirm, onSkip, deferStart = false, onFileSelected, onReset, onError },
  ref,
) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  // 입력창으로 열려있는 필드들. 한 번 열리면(빈 값이라 처음부터 열렸든, "수정" 눌러서 열었든)
  // 값이 채워져도 계속 입력창으로 유지 — 안 그러면 빈 값 필드에 타이핑해서 값이 생기는 순간
  // "이제 안 비었네?" 하고 판단해서 스스로 입력창을 닫아버려, 한 글자 치면 튕기는 것처럼 보임.
  const [openFields, setOpenFields] = useState<Set<string>>(new Set());
  const [justOpenedKey, setJustOpenedKey] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  // 법인/개인은 값이 2개뿐이라 다른 필드(텍스트 입력)와 다르게 "수정" 누르면
  // 선택 팝업이 뜨는 방식으로 처리 - state.
  const [entityTypePopupOpen, setEntityTypePopupOpen] = useState(false);

  useEffect(() => {
    if (phase !== "uploading") return;
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const reset = () => {
    // deferStart 쓰는 부모(Onboarding.tsx)는 실패해도 파일을 다시 고를 필요 없이
    // 바로 재실행할 수 있어야 하므로, 파일은 유지한 채 "selected" 단계로만 되돌린다.
    if (deferStart && file) {
      setPhase("selected");
      setErrorMessage("");
      onReset?.();
      return;
    }
    setPhase("idle");
    setFile(null);
    setErrorMessage("");
    setOpenFields(new Set());
    setJustOpenedKey(null);
    onReset?.();
  };

  // onError를 받은 부모(Onboarding.tsx)는 실패 처리를 완전히 대신하겠다는 뜻이라
  // 내부 error 페이즈는 아예 안 띄운다(그래야 팝업 안에 또 다른 화면이 겹쳐 보이는
  // 일이 없음) - onError 없으면(Signup.tsx/ProfileEdit.tsx) 기존처럼 내부에서 처리.
  const fail = (message: string) => {
    setErrorMessage(message);
    if (onError) {
      onError(message);
    } else {
      setPhase("error");
    }
  };

  const startUpload = async (target: File) => {
    setPhase("uploading");

    const formData = new FormData();
    formData.append("file", target);

    try {
      const response = await fetch(`${OCR_API_BASE_URL}/api/auth/biz-cert-ocr`, {
        method: "POST",
        body: formData,
      });
      const data: OcrResponse = await response.json();

      if (!data.ocr_success || !data.extracted) {
        fail(data.error_label ?? ERROR_FALLBACK);
        return;
      }

      setFields(data.extracted);
      // 처음부터 비어있는(=확인 필요) 필드는 처음부터 입력창으로 열어둠. 이후 값이 채워져도
      // 계속 열려있음 (openFields 자체를 이 시점 이후로는 값 기준으로 다시 계산하지 않음).
      const extracted = data.extracted;
      const initialOpen = new Set(
        REVIEW_FIELDS.filter(({ key }) => {
          const notApplicable = NOT_APPLICABLE_WHEN[key] === extracted.entity_type;
          return !notApplicable && !extracted[key];
        }).map(({ key }) => key)
      );
      setOpenFields(initialOpen);
      setPhase("review");
    } catch {
      fail("서버에 연결할 수 없습니다.");
    }
  };

  useImperativeHandle(ref, () => ({
    start: () => {
      if (file) startUpload(file);
    },
    reset,
  }));

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    event.target.value = ""; // 같은 파일 다시 선택해도 onChange 다시 뜨게
    if (!selected) return;

    const validationError = validateFile(selected);
    if (validationError) {
      setFile(null);
      setErrorMessage(validationError);
      setPhase("error");
      return;
    }

    setFile(selected);

    if (deferStart) {
      setPhase("selected");
      onFileSelected?.(selected);
      return;
    }

    await startUpload(selected);
  };

  const handleFieldChange = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = () => {
    if (!file) return;

    // DB(biz_registration_docs)가 NOT NULL로 요구하는 필드는 비어있으면 저장 자체가 실패하므로,
    // 여기서 먼저 막아서 사용자가 바로 고칠 수 있게 함.
    const missing = REQUIRED_FIELDS.filter((key) => {
      if (NOT_APPLICABLE_WHEN[key] === fields.entity_type) return false;
      return !fields[key];
    });
    if (missing.length > 0) {
      setConfirmError("빨간색으로 표시된 항목을 채워주세요.");
      return;
    }

    setConfirmError("");
    onConfirm(fields, file);
  };

  if (phase === "idle") {
    // 라벨("사업자등록증 (선택)")은 부모(회원가입 화면)에서 그리므로 여기선 드롭존만.
    return (
      <label className={styles.dropzone}>
        <input
          type="file"
          accept="image/*,.pdf"
          onChange={handleFileChange}
          className={styles.fileInput}
        />
        <span className={styles.dropTitle}>파일을 드래그하거나 클릭해서 업로드</span>
        <span className={styles.dropHint}>JPG, PNG, PDF · 최대 10MB</span>
      </label>
    );
  }

  if (phase === "selected") {
    // deferStart용 - 파일명만 보여주고 대기(부모의 "실행하기" 버튼이 ref.start()로 진행시킴).
    return (
      <div className={styles.selectedFile}>
        <span className={styles.selectedFileName}>{file?.name}</span>
        <label className={styles.selectedFileChange}>
          다른 파일 선택
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            className={styles.fileInput}
          />
        </label>
      </div>
    );
  }

  if (phase === "uploading") {
    return (
      <div className={styles.overlay}>
        <div className={styles.loadingBox} role="status" aria-live="polite">
          <div className={styles.spinner} />
          <p className={styles.loadingText}>인식 중입니다... ({elapsedSeconds}초 경과)</p>
          <p className={styles.loadingHint}>첫 요청은 모델 로딩 때문에 시간이 걸릴 수 있어요</p>
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className={styles.field}>
        <p className={styles.errorText}>{errorMessage}</p>
        <button type="button" className={styles.phaseBtn} onClick={reset}>
          다시 시도
        </button>
        <button type="button" className={styles.phaseBtn} onClick={onSkip}>
          나중에 하기
        </button>
      </div>
    );
  }

  const renderReviewRow = (key: string, label: string) => {
    // [2026-09-10] 예: 법인등록번호는 개인일 때 그냥 안 보여준다(이전엔 "-" 회색
    // 텍스트로 보여줬는데, 어차피 못 쓰는 필드를 굳이 노출할 이유가 없다는 사용자 확인).
    const notApplicable = NOT_APPLICABLE_WHEN[key] === fields.entity_type;
    if (notApplicable) return null;

    const value = fields[key] ?? "";
    const isOptional = OPTIONAL_FIELDS.has(key);
    const isOpen = openFields.has(key);
    const showWarnBadge = isOpen && !value && !isOptional; // 열려있는데 아직도 비어있으면 "확인 필요" 유지 (선택 항목 제외)

    return (
      <div key={key} className={styles.fieldRow}>
        <label>
          {label}
          {showWarnBadge && <span className={styles.badgeWarn}> 확인 필요</span>}
          {isOptional && <span className={styles.badgeMuted}> 선택 사항</span>}
        </label>

        {isOpen ? (
          // 열림 여부(openFields)는 값이 바뀌어도 다시 계산 안 함 — 안 그러면 빈 필드에
          // 타이핑해서 값이 생기는 순간 "이제 안 비었네?" 판단해서 스스로 닫혀버려
          // 한 글자 치면 튕기는 것처럼 보이는 문제가 있었음. onBlur로 자동 종료도 안 함
          // (한글 입력 중 브라우저가 순간적으로 blur를 발생시키는 경우가 있어서 동일 문제 재발 방지).
          <input
            type="text"
            value={value}
            autoFocus={justOpenedKey === key}
            onChange={(e) => handleFieldChange(key, e.target.value)}
            className={showWarnBadge ? styles.inputWarn : styles.input}
          />
        ) : (
          // [2026-09-10] 별도 "수정" 버튼 없이, 값 영역 자체를 누르면 바로 입력창으로
          // 전환되게 함(사용자 확인 - "input 누르면 수정" 방식으로).
          <button
            type="button"
            className={styles.viewText}
            onClick={() => {
              setOpenFields((prev) => new Set(prev).add(key));
              setJustOpenedKey(key);
            }}
          >
            {value}
          </button>
        )}
      </div>
    );
  };

  // phase === "review"
  return (
    <div className={styles.overlay}>
      <div className={styles.reviewBox} role="dialog" aria-modal="true" aria-label="사업자등록증 확인">
        <p className={styles.reviewDesc}>
          자동으로 인식된 정보예요. 틀린 부분이 있으면 고치고 확인을 눌러주세요.
        </p>

        {REVIEW_FIELDS.map(({ key, label }) => (
          <div key={key}>
            {renderReviewRow(key, label)}
            {key === "ceo_name" && (
              <div className={styles.fieldRow}>
                <label>법인/개인</label>
                <button
                  type="button"
                  className={styles.entityValueBtn}
                  onClick={() => setEntityTypePopupOpen(true)}
                >
                  {fields.entity_type ?? "개인"}
                  <Chevron />
                </button>
              </div>
            )}
          </div>
        ))}

        {confirmError && <p className={styles.errorText}>{confirmError}</p>}

        <button type="button" className={styles.confirmBtn} onClick={handleConfirm}>
          확인
        </button>
      </div>

      {entityTypePopupOpen && (
        <div className={styles.entityPopupOverlay} onClick={() => setEntityTypePopupOpen(false)}>
          <div
            className={styles.entityPopupCard}
            role="dialog"
            aria-modal="true"
            aria-label="법인/개인 선택"
            onClick={(e) => e.stopPropagation()}
          >
            <p className={styles.entityPopupTitle}>법인/개인 선택</p>
            {["법인", "개인"].map((option) => (
              <button
                key={option}
                type="button"
                className={styles.entityOption}
                onClick={() => {
                  handleFieldChange("entity_type", option);
                  setEntityTypePopupOpen(false);
                }}
              >
                <span
                  className={`${styles.radio} ${(fields.entity_type ?? "개인") === option ? styles.radioOn : ""}`}
                  aria-hidden="true"
                />
                {option}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

export default BizCertUpload;
