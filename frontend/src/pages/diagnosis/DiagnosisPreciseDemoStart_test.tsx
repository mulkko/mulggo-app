import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import { clearDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import { DEMO_TYPING_KEY } from "./DiagnosisTextQuestion";
import { setSession } from "../../auth/session";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// [2026-09-14, 개인 확인용 - 시연 영상 촬영용] 이름/업종코드/지역까지 미리 채워둔
// 전용 데모 계정 (backend에 직접 스크립트로 생성 - 회원가입 화면을 거치지 않음).
// 실제 서비스 사용자 데이터 아님, 테스트 전용 계정.
const DEMO_ACCOUNT = { email: "demo@mulkko.test", password: "Demo1234!" };

/**
 * [2026-09-14, 개인 확인용 - 시연 영상 촬영용] "정밀 구체화" 진단 전체 흐름을
 * 실제 라이브 화면(Step1~9 등, 원본 그대로) 그대로 타면서, 매 문항을 직접 타이핑/
 * 복붙하지 않아도 되게 하려고 만든 진입 페이지. 이 페이지 자체는 진짜 화면이
 * 아니라 "데모 답변으로 sessionStorage를 미리 채우고 /diagnosis/1로 보내는" 버튼
 * 하나짜리 스크립트에 가깝다.
 *
 * 동작:
 * 1) clearDiagnosisAnswers()로 깨끗이 비우고(재촬영 시에도 항상 같은 상태로 시작),
 * 2) Q1~Q10 + 지역 전부를 미리 써둔 데모 답변으로 saveDiagnosisAnswers,
 * 3) DiagnosisTextQuestion.tsx가 보는 DEMO_TYPING_KEY 플래그를 켠다 - 이 플래그가
 *    있으면 그 컴포넌트가 initialValue를 한 글자씩 타이핑되는 것처럼 보여준다
 *    (실제 코드는 DiagnosisTextQuestion.tsx 상단 주석 참고, 일반 사용자 흐름엔
 *    전혀 영향 없음 - 이 페이지에서만 플래그를 켬).
 * 4) /diagnosis/1(실제 라이브 화면)로 이동 - 이후 Q2(출발점 선택)/Q5(매장형태)/
 *    Q6(지역)처럼 텍스트가 아니라 선택형인 화면들도, 전부 기존 화면이 마운트 시
 *    sessionStorage 값을 읽어 미리 선택해두는 방식이라(Step5.tsx의 sido/sigungu/dong
 *    복원과 동일 패턴) 이 페이지를 더 손댈 필요 없이 그대로 미리 채워진 채로 보인다.
 *
 * "확인하기" 버튼(요약 화면 → POST /api/diagnosis/start)부터는 실제 백엔드 매칭/분석이
 * 그대로 돌아간다 - 데모라고 결과까지 가짜로 만들지 않는다(진짜 리포트가 나옴).
 */
// [2026-09-14, 사용자 확인] E:\3차프로젝트\기술창업_답안지.txt 내용 그대로 - 카페/
// 오프라인 시나리오에서 기술창업(온라인) 시나리오로 교체. 이 답안지의 기대 매칭
// 결과는 resolvedKsicCodes: ["58222","62090","85699"](응용 소프트웨어 개발 및 공급업 /
// 컴퓨터 관련 서비스업 / 기타 교육 서비스업).
const DEMO_ANSWERS = {
  mode: "precise" as const,
  origin: "problem" as const,
  seedInterest:
    "재고관리가 어려운 소상공인을 위한 재고관리 앱을 직접 개발해서 구독료로 제공하고, 동네 소상공인과 배달기사님을 연결해주는 중개 플랫폼도 같이 운영하며, 소상공인을 위한 온라인 회계·세무 강의 콘텐츠도 구독형으로 함께 제공하려고 합니다.",
  problemToSolve:
    "소상공인들은 재고관리를 엑셀이나 수기로 해서 비효율적이고, 배달이 필요한데 배달대행 기사님과 바로 연결할 방법이 마땅치 않으며, 회계·세무 지식이 없어 어려움을 겪는 경우도 많습니다.",
  solutionApproach:
    "재고관리 SaaS 앱을 직접 개발해서 월 구독료를 받고, 소상공인과 배달기사님을 앱으로 연결해서 매칭 수수료를 받으며, 별도로 회계·세무 실무를 알려주는 온라인 강의를 직접 제작해 구독료를 받고 제공합니다.",
  storeType: "digital" as const,
  sido: "부산광역시",
  sigungu: "서구",
  dong: "",
  target: "재고관리에 어려움을 겪는 동네 소상공인 사장님들과, 배달 콜을 안정적으로 받고 싶은 배달대행 기사님들",
  differentiator:
    "범용 회계 프로그램과 달리 소상공인 재고관리에 특화됐고, 배달 중개와 회계 교육까지 한 앱에서 같이 제공하는 점",
  revenueModel: "재고관리 앱 월 구독료, 배달 매칭 수수료, 회계·세무 강의 구독료 세 가지로 수익을 냅니다",
  coreSkill: "스타트업에서 3년간 백엔드 개발자로 근무한 경험이 있고, 세무사 자격증을 보유하고 있습니다",
};

function DiagnosisPreciseDemoStart_test() {
  const navigate = useNavigate();
  const [loginState, setLoginState] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");

  // [2026-09-14, 사용자 확인] 버튼 누른 시점에 로그인까지 기다리면 촬영 중 그 지연이
  // 그대로 보인다 - 페이지 진입하자마자(마운트 시) 미리 로그인해두고, 버튼은 답변
  // 채우기+이동만 하게 분리했다. 데모 계정으로 실제 로그인(POST /api/auth/login)을
  // 안 해두면 요약 화면 "확인하기"(POST /start)가 401로 막히거나, 그 브라우저에
  // 원래 로그인돼 있던 다른 계정으로 진행돼버림.
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(DEMO_ACCOUNT),
    })
      .then((res) => res.json())
      .then(
        (body: {
          success: boolean;
          data?: { user_id: number; email: string; name: string; token: string };
          error?: { message: string };
        }) => {
          if (!body.success || !body.data) {
            throw new Error(body.error?.message || "데모 계정 로그인에 실패했어요.");
          }
          setSession(body.data.token, body.data.user_id, body.data.email);
          setLoginState("ready");
        },
      )
      .catch((e) => {
        setError(e instanceof Error ? e.message : "데모 계정 로그인에 실패했어요.");
        setLoginState("error");
      });
  }, []);

  const start = (typing: boolean) => {
    clearDiagnosisAnswers();
    saveDiagnosisAnswers(DEMO_ANSWERS);
    if (typing) {
      sessionStorage.setItem(DEMO_TYPING_KEY, "1");
    } else {
      sessionStorage.removeItem(DEMO_TYPING_KEY);
    }
    navigate("/diagnosis/1");
  };

  return (
    <div className={`pageContainer ${styles.page}`} style={{ padding: 24, gap: 16, display: "flex", flexDirection: "column" }}>
      <h1 style={{ fontSize: 18, fontWeight: 800 }}>[개인 확인용] 정밀진단 시연 데모</h1>
      <p style={{ fontSize: 13, color: "#8B8D93", lineHeight: 1.6 }}>
        데모 전용 계정(김창업 · 소상공인 재고관리 플랫폼 · 응용 소프트웨어 개발 및 공급업)으로 {loginState === "ready" ? "이미 로그인돼 있습니다" : "로그인 중입니다"}.
        아래 버튼을 누르면 Q1~Q10 + 지역 답변이 전부 미리 채워진 채로 실제 진단 화면(/diagnosis/1)으로
        이동합니다. 그 다음부터는 각 화면에서 "다음" 버튼만 누르면서 촬영하면 됩니다. 업종코드 확인/분석
        리포트는 진짜로 백엔드가 돌립니다(가짜 결과 아님).
      </p>
      <button type="button" className={styles.nextButton} disabled={loginState !== "ready"} onClick={() => start(true)}>
        {loginState === "loading" ? "로그인 준비 중..." : "타이핑 애니메이션으로 시작"}
      </button>
      <button type="button" className={styles.prevButton} disabled={loginState !== "ready"} onClick={() => start(false)}>
        그냥 바로 다 채워서 시작 (애니메이션 없음)
      </button>
      {error && <p className={styles.errorText}>{error}</p>}
    </div>
  );
}

export default DiagnosisPreciseDemoStart_test;
