import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/customerSupport.module.css";

/**
 * 고객센터 챗봇 화면.
 *
 * backend/api/support.py(POST /api/support/chat)는 이미 완성돼 있었는데(고객센터
 * 챗봇 로직 자체는 backend/customer_chatbot/) 붙는 프론트 화면이 없어서, 기능이
 * 되는 걸 바로 테스트해볼 수 있게 최소 형태로 만듦(디자인 시안 없음, 2026-09-10).
 *
 * 상태 없는(stateless) API라 대화 맥락은 안 쌓인다 - 질문 한 건마다 독립적으로 답변.
 * needs_human_support가 true인 답변 밑에는 안내 문구만 보여준다(문의 폼은 아직 없음 - TODO).
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type ChatMessage = {
  role: "user" | "bot";
  text: string;
  needsHumanSupport?: boolean;
};

const INITIAL_MESSAGE: ChatMessage = {
  role: "bot",
  text: "안녕하세요! 물꼬 고객센터입니다. 궁금하신 점을 입력해주세요.",
};

function CustomerSupport() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleBack = () => {
    navigate(-1);
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setError("");
    setSending(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/support/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
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

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") handleSend();
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
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
        <span className={styles.headerTitle}>고객센터</span>
      </header>

      <main className={styles.chatArea}>
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? styles.userBubbleRow : styles.botBubbleRow}>
            {message.role === "user" ? (
              <p className={styles.userBubble}>{message.text}</p>
            ) : (
              <div>
                <p className={styles.botBubble}>{message.text}</p>
                {message.needsHumanSupport && (
                  <p className={styles.humanHint}>더 자세한 문의는 담당자 확인이 필요해요(문의 폼 준비 중).</p>
                )}
              </div>
            )}
          </div>
        ))}
        {error && <p className={styles.errorText}>{error}</p>}
        <div ref={bottomRef} />
      </main>

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
        >
          {sending ? "..." : "전송"}
        </button>
      </div>
    </div>
  );
}

export default CustomerSupport;
