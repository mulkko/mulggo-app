import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import SelectSheet from "../../components/SelectSheet/SelectSheet";

/**
 * [개인 디자인 확인용, 원본 DiagnosisStep5.tsx(Q6 · 지역·규모)의 격리 사본] 이전 단계
 * 답변·GET /analysis/regions 호출 없이 목업 지역 목록으로 바로 확인(2026-09-13,
 * 사용자 확인 - 나머지 _test 사본과 동일 패턴).
 */
const SIDO_OPTIONS = [{ label: "서울특별시", value: "서울특별시" }];
const SIGUNGU_OPTIONS = [{ label: "종로구", value: "종로구" }];
const DONG_OPTIONS = [{ label: "청운효자동", value: "청운효자동" }];

function DiagnosisStep5_test() {
  const navigate = useNavigate();
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");

  const canSubmit = sido !== "" && sigungu !== "" && dong !== "";

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="92%" stepLabel="AI 제안 · 6/6 [TEST]" />
      <div className={styles.scrollArea}>
        <span className={styles.topicBadge}>Q6 · 지역·규모</span>
        <h1 className={styles.questionTitle}>어디서, 어느 정도 규모로 시작하실 계획인가요?</h1>
        <p className={styles.questionSub}>시/도 → 시/군/구 → 행정동 순서로 선택해주세요.</p>
        <div className={styles.regionGroup}>
          <SelectSheet
            label="시/도"
            name="sido"
            value={sido}
            options={SIDO_OPTIONS}
            onChange={(v) => {
              setSido(v);
              setSigungu("");
              setDong("");
            }}
            placeholder="시/도 선택"
          />
          <SelectSheet
            label="시/군/구"
            name="sigungu"
            value={sigungu}
            options={SIGUNGU_OPTIONS}
            onChange={(v) => {
              setSigungu(v);
              setDong("");
            }}
            placeholder="시/군/구 선택"
            disabled={!sido}
          />
          <SelectSheet
            label="행정동"
            name="dong"
            value={dong}
            options={DONG_OPTIONS}
            onChange={setDong}
            placeholder="행정동 선택"
            disabled={!sigungu}
          />
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={() => navigate("/home")}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={!canSubmit} onClick={() => {}}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisStep5_test;
