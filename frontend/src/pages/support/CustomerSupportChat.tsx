import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/customerSupportChat.module.css";
import BottomNav from "../../components/BottomNav/BottomNav";
import BackButton from "../../components/BackButton/BackButton";
import chatAvatarIcon from "../../assets/9_mint.svg";

/**
 * 고객센터 챗봇 화면 (19-1번, /support/chat). 19번 "1:1 문의"(CustomerSupport.tsx)의 하위 화면.
 *
 * backend/api/support.py(POST /api/support/chat)는 이미 완성돼 있었는데(고객센터
 * 챗봇 로직 자체는 backend/customer_chatbot/) 붙는 프론트 화면이 없어서, 기능이
 * 되는 걸 바로 테스트해볼 수 있게 최소 형태로 만듦(디자인 시안 없음, 2026-09-10).
 * 2026-09-11: 프로토타입 실측값 기준으로 디자인 업그레이드(칩/아바타/pill 등),
 * 백엔드 연동 로직은 변경 없음. 이후 19번/19-1번으로 화면 분리하면서 파일명을
 * CustomerSupportChat.tsx로 변경(라우트: /support -> 19번, /support/chat -> 19-1번).
 *
 * 상태 없는(stateless) API라 대화 맥락은 안 쌓인다 - 질문 한 건마다 독립적으로 답변.
 * needs_human_support가 true인 답변 밑에는 안내 문구만 보여준다(문의 접수는 /support로 안내).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type ChatMessage = {
  role: "user" | "bot";
  text: string;
  needsHumanSupport?: boolean;
};

const INITIAL_MESSAGE: ChatMessage = {
  role: "bot",
  text: "안녕하세요! 물꼬 서비스 도우미 물꼬미에요. 아래 주제를 눌러보거나 궁금한 점을 자유롭게 물어보세요.",
};

const FAQ_CHIPS = [
  { label: "사업 아이디어 입력", question: "사업 아이디어는 몇 가지 질문에 답하면 되나요?" },
  { label: "업종코드 확인", question: "업종코드는 어떻게 확인되나요?" },
  { label: "아이디어 추천", question: "추천 아이디어를 보면 제 원래 계획이 바뀌나요?" },
  { label: "지원사업 매칭", question: "지원사업 필터에는 어떤 항목들이 있나요?" },
  { label: "분석 리포트", question: "분석 리포트에서는 어떤 내용을 확인할 수 있나요?" },
  { label: "마이페이지", question: "마이페이지에서는 뭘 확인할 수 있나요?" },
  { label: "문의하기", question: "문의하면 챗봇이 바로 답변을 주나요?" },
  { label: "회원가입·사업자등록증", question: "사업자등록증 인식이 잘 안되면 어떻게 하나요?" },
  { label: "신청서 자동입력(채우기)", question: "채우기 기능은 어떻게 작동하나요?" },
];

export function BotAvatarIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="#FFFFFF"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="#FFFFFF"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
    </svg>
  );
}

function CustomerSupportChat() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const handleBack = () => {
    navigate(-1);
  };

  const sendMessage = async (question: string) => {
    const q = question.trim();
    if (!q || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setError("");
    setSending(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const body: {
        success: boolean;
        data?: { answer: string; needs_human_support: boolean };
        error?: { message: string };
      } = await res.json();

      if (body.success && body.data) {
        setMessages((prev) => [
          ...prev,
          { role: "bot", text: body.data!.answer, needsHumanSupport: body.data!.needs_human_support },
        ]);
      } else {
        setError(body.error?.message ?? "답변을 가져오지 못했어요.");
      }
    } catch {
      setError("서버에 연결할 수 없어요.");
    } finally {
      setSending(false);
    }
  };

  const handleSend = () => sendMessage(input);
  const handleChipClick = (question: string) => sendMessage(question);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") handleSend();
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <BackButton onClick={handleBack} />
        <span className={styles.headerAvatar}>
          <img className={styles.headerAvatarImg} src={chatAvatarIcon} alt="" />
        </span>
        <span className={styles.headerTitle}>챗봇 상담</span>
      </header>

      <main className={styles.chatArea}>
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? styles.userBubbleRow : styles.botBubbleRow}>
            {message.role === "user" ? (
              <p className={styles.userBubble}>{message.text}</p>
            ) : (
              <span className={styles.botAvatar}>
                <img className={styles.botAvatarImg} src={chatAvatarIcon} alt="" />
              </span>
            )}
            {message.role === "bot" && (
              <div>
                <p className={styles.botBubble}>{message.text}</p>
                {message.needsHumanSupport && (
                  <p className={styles.humanHint}>문의 접수 화면은 준비 중이에요</p>
                )}
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className={styles.botBubbleRow}>
            <span className={styles.botAvatar}>
              <img className={styles.botAvatarImg} src={chatAvatarIcon} alt="" />
            </span>
            <p className={styles.loadingBubble}>답변을 준비하고 있어요...</p>
          </div>
        )}
        {error && <p className={styles.errorText}>{error}</p>}
        <div ref={bottomRef} />
      </main>

      <div className={styles.chipRow}>
        {FAQ_CHIPS.map((chip) => (
          <button
            key={chip.label}
            type="button"
            className={styles.chip}
            onClick={() => handleChipClick(chip.question)}
            disabled={sending}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div className={styles.inputBar}>
        <input
          className={styles.input}
          type="text"
          placeholder="궁금한 점을 입력해주세요"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          type="button"
          className={styles.sendButton}
          onClick={handleSend}
          disabled={sending || !input.trim()}
          aria-label="전송"
        >
          <SendIcon />
        </button>
      </div>

      <BottomNav active="my" />
    </div>
  );
}

export default CustomerSupportChat;
