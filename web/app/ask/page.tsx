"use client";

import { useState } from "react";
import { api, type AskResponse } from "../../lib/api";
import { ApiDownBanner } from "../api-status";

const EXAMPLES = [
  "Chu trình Euler là gì?",
  "Khi nào dùng kiểm định t thay vì z?",
  "Ma trận nghịch đảo tính thế nào?",
  "Tích phân từng phần dùng khi nào?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    if (!text.trim()) return;
    setQuestion(text);
    setAsked(text.trim());
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.ask(text.trim()));
      setDown(false);
    } catch (exc) {
      setError((exc as Error).message);
      setDown(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Hỏi lý thuyết</h1>
      <p className="lead">
        Câu trả lời chỉ dựa trên giáo trình đã nạp và <strong>luôn kèm nguồn</strong> để
        em tự kiểm. Hỏi ngoài phạm vi bốn môn thì hệ thống nói thẳng là không có, không
        đoán bừa.
      </p>

      {down && <ApiDownBanner />}

      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <label htmlFor="q">Câu hỏi</label>
        <div className="row" style={{ gap: 8, alignItems: "stretch" }}>
          <input
            id="q"
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="ví dụ: định lý giới hạn trung tâm nói gì?"
            autoComplete="off"
            style={{ flex: "1 1 240px" }}
          />
          <button type="submit" disabled={busy || !question.trim()}>
            {busy && <span className="spin" aria-hidden="true" />}
            {busy ? "Đang tra…" : "Hỏi"}
          </button>
        </div>

        <p className="meta" style={{ margin: "14px 0 7px" }}>Thử nhanh:</p>
        <div className="row tight">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="secondary small"
              onClick={() => void ask(example)}
              disabled={busy}
            >
              {example}
            </button>
          ))}
        </div>

        <p className="meta" style={{ marginTop: 14 }}>
          Giáo trình phần lớn là tiếng Anh, nên hỏi bằng thuật ngữ tiếng Anh hiện vẫn cho
          kết quả tốt hơn — đo được ở EXP-4: Recall@5 là 0,98 với câu hỏi tiếng Anh so với
          0,60 với tiếng Việt.
        </p>

        {error && <p className="error">{error}</p>}
      </form>

      {busy && (
        <div className="panel">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton w60" />
        </div>
      )}

      {answer && (
        <>
          <div className="panel">
            <div className="row spread" style={{ marginBottom: 12 }}>
              <span className={`chip ${answer.in_scope ? "ok" : "warn"}`}>
                {answer.in_scope ? "Trong phạm vi giáo trình" : "Ngoài phạm vi"}
              </span>
              <span className="meta">Câu hỏi: “{asked}”</span>
            </div>
            <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{answer.answer}</p>
            <p className="meta" style={{ marginTop: 14 }}>
              {answer.used_llm
                ? "Mô hình diễn đạt lại, nội dung lấy từ các nguồn bên dưới."
                : "Trích thẳng từ giáo trình (chưa bật mô hình diễn đạt)."}
            </p>
          </div>

          {answer.sources.length > 0 && (
            <>
              <h2>Nguồn ({answer.sources.length})</h2>
              {answer.sources.map((source, index) => (
                <div className="source" key={`${source}-${index}`}>
                  <div className="where">Nguồn {index + 1}</div>
                  {source}
                </div>
              ))}
            </>
          )}
        </>
      )}
    </main>
  );
}
