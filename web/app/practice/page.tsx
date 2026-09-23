"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import katex from "katex";
import { api, type AttemptResponse, type Hint, type PublicItem } from "../../lib/api";
import { loadSession, type StoredSession } from "../../lib/session";

/** Công thức trong đề: có LaTeX thì render, không thì hiện nguyên văn tiếng Việt. */
function Statement({ item }: { item: PublicItem }) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    if (!item.statement_latex) {
      setHtml(null);
      return;
    }
    try {
      setHtml(katex.renderToString(item.statement_latex, { displayMode: true, throwOnError: false }));
    } catch {
      setHtml(null); // LaTeX hỏng thì vẫn phải đọc được đề, không để màn hình trắng
    }
  }, [item]);

  return (
    <>
      <p className="statement">{item.statement_vi}</p>
      {html && <div dangerouslySetInnerHTML={{ __html: html }} />}
    </>
  );
}

const ANSWER_HELP: Record<string, string> = {
  expression: "Nhập biểu thức, ví dụ x**2/2 + C",
  antiderivative: "Nhập nguyên hàm, nhớ + C",
  number: "Nhập một số, phân số cũng được (3/4)",
  set: "Các phần tử cách nhau bởi dấu phẩy: 1, 3",
  matrix: "Ma trận [[1, 2], [3, 4]] hoặc vector [1, 2]",
  eigenvector: "Vector [1, 2] — chấp nhận mọi bội vô hướng",
  linear_system: "Nghiệm [2, 1], hoặc viết 'vô nghiệm'",
  boolean: "Trả lời có / không",
  text: "Trả lời bằng lời",
};

export default function PracticePage() {
  const router = useRouter();
  const [session, setSession] = useState<StoredSession | null>(null);
  const [item, setItem] = useState<PublicItem | null>(null);
  const [answer, setAnswer] = useState("");
  const [steps, setSteps] = useState("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [hint, setHint] = useState<Hint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const nextItem = useCallback(
    async (current: StoredSession) => {
      setBusy(true);
      setError(null);
      try {
        const next = await api.nextItem(current.userId, current.subject);
        setItem(next);
        setAnswer("");
        setSteps("");
        setResult(null);
        setHint(null);
      } catch (exc) {
        setError((exc as Error).message);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  useEffect(() => {
    const saved = loadSession();
    if (!saved) {
      router.push("/");
      return;
    }
    setSession(saved);
    void nextItem(saved);
  }, [router, nextItem]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!session || !item) return;
    setBusy(true);
    setError(null);
    try {
      const lines = steps.split("\n").map((s) => s.trim()).filter(Boolean);
      const response = await api.submit(session.sessionId, item.item_id, answer.trim(), lines);
      setResult(response);
      setHint(response.hint ?? null);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function askHint(solution = false) {
    if (!session || !item) return;
    setBusy(true);
    try {
      setHint(await api.hint(session.sessionId, item.item_id, solution));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!session) return <main><p>Đang tải…</p></main>;

  return (
    <main>
      <div className="row spread">
        <h1>Luyện tập — {session.subject}</h1>
        <span className="meta">{session.userId}</span>
      </div>

      {error && <p className="error">{error}</p>}

      {item && (
        <>
          <div className="panel">
            <Statement item={item} />
            <p className="meta">
              {item.item_id} · kỹ năng: {item.skills.join(", ") || "—"} · độ khó{" "}
              {item.difficulty.toFixed(2)}
            </p>
          </div>

          <form className="panel" onSubmit={submit}>
            <label htmlFor="answer">Đáp án cuối</label>
            <input
              id="answer"
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={ANSWER_HELP[item.answer_type] ?? "Nhập đáp án"}
              autoComplete="off"
            />

            <label htmlFor="steps" style={{ marginTop: 12 }}>
              Các bước làm (tuỳ chọn, mỗi dòng một bước — có bước thì hệ thống chỉ được
              chỗ sai đầu tiên)
            </label>
            <textarea
              id="steps"
              value={steps}
              onChange={(e) => setSteps(e.target.value)}
              placeholder={"u = x**2 + 1\ndu = 2*x dx"}
            />

            <div className="row" style={{ marginTop: 12 }}>
              <button type="submit" disabled={busy || !answer.trim()}>
                Nộp bài
              </button>
              <button type="button" className="secondary" onClick={() => askHint(false)} disabled={busy}>
                {hint ? "Gợi ý thêm" : "Xin gợi ý"}
              </button>
              <button type="button" className="secondary" onClick={() => void nextItem(session)} disabled={busy}>
                Bài khác
              </button>
            </div>
          </form>
        </>
      )}

      {result && (
        <div className={`verdict ${result.is_correct ? "ok" : "wrong"}`}>
          <strong>{result.is_correct ? "Đúng rồi" : "Chưa đúng"}</strong> — {result.message}
          {result.first_wrong_step !== null && (
            <div className="meta">Bước sai đầu tiên: bước {result.first_wrong_step}</div>
          )}
          {result.placement_mode && (
            <div className="meta">
              Đang đo đầu vào, còn {result.placement_remaining} câu.
            </div>
          )}
          {result.is_correct && (
            <div className="row" style={{ marginTop: 10 }}>
              <button type="button" onClick={() => void nextItem(session)}>
                Bài tiếp theo
              </button>
            </div>
          )}
        </div>
      )}

      {hint && (
        <div className="hint">
          <div className="level">
            Gợi ý mức {hint.level} · {hint.level_label}
            {hint.source === "llm" ? " · do mô hình diễn đạt" : " · mẫu có sẵn"}
          </div>
          <div>{hint.text}</div>
          {hint.level < 5 && (
            <div className="row" style={{ marginTop: 8 }}>
              <button type="button" className="secondary" onClick={() => askHint(false)} disabled={busy}>
                Vẫn chưa hiểu, gợi ý thêm
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
