"use client";

import { useState } from "react";
import { api, type AskResponse } from "../../lib/api";

const EXAMPLES = [
  "Chu trình Euler là gì?",
  "Khi nào dùng kiểm định t thay vì z?",
  "Ma trận nghịch đảo tính thế nào?",
  "Tích phân từng phần dùng khi nào?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    if (!text.trim()) return;
    setQuestion(text);
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.ask(text.trim()));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Hỏi lý thuyết</h1>
      <p className="lead">
        Câu trả lời chỉ dựa trên giáo trình đã nạp và luôn kèm nguồn để em tự kiểm.
        Hỏi ngoài phạm vi bốn môn thì hệ thống nói thẳng là không có, không đoán bừa.
      </p>

      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="q">Câu hỏi</label>
        <input
          id="q"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="ví dụ: định lý giới hạn trung tâm nói gì?"
          autoComplete="off"
        />
        <div className="row" style={{ marginTop: 12 }}>
          <button type="submit" disabled={busy || !question.trim()}>
            {busy ? "Đang tra giáo trình…" : "Hỏi"}
          </button>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="secondary"
              onClick={() => void ask(example)}
              disabled={busy}
            >
              {example}
            </button>
          ))}
        </div>
        {error && <p className="error">{error}</p>}
      </form>

      {answer && (
        <div className={`panel ${answer.in_scope ? "" : "meta"}`}>
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{answer.answer}</p>
          {answer.sources.length > 0 && (
            <>
              <h2>Nguồn</h2>
              <ul className="meta" style={{ margin: 0, paddingLeft: 18 }}>
                {answer.sources.map((source, index) => (
                  <li key={`${source}-${index}`}>{source}</li>
                ))}
              </ul>
            </>
          )}
          <p className="meta" style={{ marginBottom: 0 }}>
            {answer.used_llm ? "Diễn đạt lại bởi mô hình, nội dung lấy từ các nguồn trên."
                             : "Trích thẳng từ giáo trình (chưa bật mô hình diễn đạt)."}
          </p>
        </div>
      )}
    </main>
  );
}
