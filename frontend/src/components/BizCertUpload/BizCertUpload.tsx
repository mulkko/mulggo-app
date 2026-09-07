import { useState } from "react";
import type { ChangeEvent } from "react";
import styles from "./bizCertUpload.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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
];

// 법인/개인 구분에 따라 애초에 존재하지 않는 필드 (법인등록번호는 법인만, 생년월일은 개인만).
const NOT_APPLICABLE_WHEN: Record<string, string> = {
  corp_no: "개인",
  birth_date: "법인",
};

// DB(biz_registration_docs)가 NOT NULL로 요구하는 필드 — 확인 버튼 누르기 전에 채워져 있어야 함.
const REQUIRED_FIELDS = ["company_name", "ceo_name", "biz_no", "open_date", "business_address"];

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
}

type Phase = "idle" | "uploading" | "error" | "review";

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

function BizCertUpload({ onConfirm, onSkip }: BizCertUploadProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [editingKey, setEditingKey] = useState<string | null>(null);

  const reset = () => {
    setPhase("idle");
    setFile(null);
    setErrorMessage("");
    setEditingKey(null);
  };

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
    setPhase("uploading");

    const formData = new FormData();
    formData.append("file", selected);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/biz-cert-ocr`, {
        method: "POST",
        body: formData,
      });
      const data: OcrResponse = await response.json();

      if (!data.ocr_success || !data.extracted) {
        setErrorMessage(data.error_label ?? ERROR_FALLBACK);
        setPhase("error");
        return;
      }

      setFields(data.extracted);
      setPhase("review");
    } catch {
      setErrorMessage("서버에 연결할 수 없습니다.");
      setPhase("error");
    }
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
      alert("빨간색으로 표시된 항목을 채워주세요.");
      return;
    }

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

  if (phase === "uploading") {
    return (
      <div className={styles.field}>
        <p>인식 중입니다... (첫 요청은 시간이 걸릴 수 있어요)</p>
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

  // phase === "review"
  return (
    <div className={styles.reviewBox}>
      <p className={styles.reviewDesc}>
        자동으로 인식된 정보예요. 틀린 부분이 있으면 고치고 확인을 눌러주세요.
      </p>

      {REVIEW_FIELDS.map(({ key, label }) => {
        const value = fields[key] ?? "";
        const notApplicable = NOT_APPLICABLE_WHEN[key] === fields.entity_type;
        const needsCheck = !value && !notApplicable;
        const isEditing = editingKey === key;

        return (
          <div key={key} className={styles.fieldRow}>
            <label>
              {label}
              {needsCheck && <span className={styles.badgeWarn}> 확인 필요</span>}
              {notApplicable && <span className={styles.badgeMuted}> 해당 없음</span>}
            </label>

            {notApplicable ? (
              <div className={styles.viewTextMuted}>-</div>
            ) : needsCheck || isEditing ? (
              <input
                type="text"
                value={value}
                autoFocus={isEditing}
                onChange={(e) => handleFieldChange(key, e.target.value)}
                onBlur={() => setEditingKey(null)}
                className={needsCheck ? styles.inputWarn : styles.input}
              />
            ) : (
              <div className={styles.viewRow}>
                <span className={styles.viewText}>{value}</span>
                <button
                  type="button"
                  className={styles.editBtn}
                  onClick={() => setEditingKey(key)}
                >
                  수정
                </button>
              </div>
            )}
          </div>
        );
      })}

      <button type="button" className={styles.confirmBtn} onClick={handleConfirm}>
        확인
      </button>
    </div>
  );
}

export default BizCertUpload;
