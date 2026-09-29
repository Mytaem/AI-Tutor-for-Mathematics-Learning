"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import katex from "katex";
import { api, type AttemptResponse, type Hint, type PublicItem } from "../../lib/api";
import { loadSession, type StoredSession } from "../../lib/session";
import { ApiDownBanner } from "../api-status";

/** Công thức trong đề: có LaTeX thì render, không thì hiện nguyên văn tiếng Việt. */
function Statement({ item }: { item: PublicItem }) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    if (!item.statement_latex) {
      setHtml(null);
      return;
    }
    try {
      setHtml(
        katex.renderToString(item.statement_latex, { displayMode: true, throwOnError: false })
      );
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
  expression: "Biểu thức, ví dụ x**2/2 + C",
  antiderivative: "Nguyên hàm, nhớ + C",
  number: "Một số — viết 0.75 hay 0,75 đều được, phân số 3/4 cũng được",
  set: "Các phần tử cách nhau bởi dấu phẩy: 1, 3",
  matrix: "Ma trận [[1, 2], [3, 4]] hoặc vector [1, 2]",
  eigenvector: "Vector [1, 2] — chấp nhận mọi bội vô hướng",
  linear_system: "Nghiệm [2, 1] hoặc x = 2, y = 1; vô nghiệm thì viết bằng lời",
  ode_solution: "Nghiệm kèm hằng số tự do, ví dụ C1*exp(x)",
  boolean: "Trả lời có / không",
  text: "Trả lời bằng lời",
};

const DIFFICULTY = (value: number) =>
  value < 0.35 ? "dễ" : value < 0.65 ? "vừa" : "khó";

/** Năm vạch cho năm mức gợi ý — người học thấy được còn bao nhiêu mức để xin. */
function Ladder({ level }: { level: number }) {
  return (
    <span className="ladder" role="img" aria-label={`Gợi ý mức ${level} trên 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <i key={n} className={n <= level ? "on" : ""} />
      ))}
    </span>
  );
}

export default function PracticePage() {
  const router = useRouter();
  const [session, setSession] = useState<StoredSession | null>(null);
  const [item, setItem] = useState<PublicItem | null>(null);
  const [answer, setAnswer] = useState("");
  const [steps, setSteps] = useState("");
  const [showSteps, setShowSteps] = useState(false);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [hint, setHint] = useState<Hint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [solved, setSolved] = useState(0);
  const answerBox = useRef<HTMLInputElement>(null);

  const nextItem = useCallback(async (current: StoredSession) => {
    setBusy(true);
    setError(null);
    try {
      const next = await api.nextItem(current.userId, current.subject);
      setItem(next);
      setAnswer("");
      setSteps("");
      setShowSteps(false);
      setResult(null);
      setHint(null);
      setDown(false);
      // Con trỏ nhảy thẳng vào ô đáp án: luyện tập là gõ liên tục, bắt người
      // học với chuột sau mỗi bài là chỗ rò thời gian lớn nhất của màn hình này.
      window.setTimeout(() => answerBox.current?.focus(), 30);
    } catch (exc) {
      setError((exc as Error).message);
      setDown(true);
    } finally {
      setBusy(false);
    }
  }, []);

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
    if (!session || !item || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const lines = steps.split("\n").map((s) => s.trim()).filter(Boolean);
      const response = await api.submit(session.sessionId, item.item_id, answer.trim(), lines);
      setResult(response);
      setHint(response.hint ?? null);
      if (response.is_correct) setSolved((n) => n + 1);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function askHint(solution = false) {
    if (!session || !item) return;
    setBusy(true);
    setError(null);
    try {
      setHint(await api.hint(session.sessionId, item.item_id, solution));
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!session) {
    return (
      <main>
        <div className="panel">
          <div className="skeleton tall w60" />
          <div className="skeleton" />
          <div className="skeleton w40" />
        </div>
      </main>
    );
  }

  return (
    <main>
      <div className="row spread" style={{ marginBottom: 18 }}>
        <div>
          <h1 style={{ marginBottom: 2 }}>Luyện tập</h1>
          <div className="meta">
            {session.subject} · {session.userId}
            {solved > 0 && ` · đã làm đúng ${solved} bài trong phiên này`}
          </div>
        </div>
        <button type="button" className="ghost small" onClick={() => router.push("/progress")}>
          Xem tiến độ →
        </button>
      </div>

      {down && <ApiDownBanner />}

      {result?.placement_mode && (
        <div className="chip accent" style={{ marginBottom: 14 }}>
          Đang đo đầu vào — còn {result.placement_remaining} câu
        </div>
      )}

      {item ? (
        <>
          <div className="panel flush">
            {/* Chip nào cũng phải nói NÓ LÀ GÌ. "MAE101-LA-SYS-001" và "vừa"
                đứng trơ ra thì người học không biết đang đọc mã đề hay mã kỹ
                năng, cũng không biết "vừa" là vừa cái gì. */}
            <div className="panel-head">
              <span className="chip">
                Mã đề <span className="mono">{item.item_id}</span>
              </span>
              <span className="chip">Độ khó: {DIFFICULTY(item.difficulty)}</span>
              {item.skills.length > 0 && (
                <span className="chip accent">
                  Kỹ năng: {item.skills.join(", ")}
                </span>
              )}
            </div>
            <div className="panel-body">
              <Statement item={item} />
            </div>
          </div>

          <form className="panel" onSubmit={submit}>
            <label htmlFor="answer">Đáp án cuối</label>
            <input
              id="answer"
              ref={answerBox}
              className="answer"
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="gõ đáp án rồi nhấn Enter"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
            />
            <p className="meta" style={{ marginTop: 7 }}>
              {ANSWER_HELP[item.answer_type] ?? "Nhập đáp án"}
            </p>

            {showSteps ? (
              <div style={{ marginTop: 16 }}>
                <label htmlFor="steps">
                  Các bước làm — mỗi dòng một bước
                </label>
                <textarea
                  id="steps"
                  value={steps}
                  onChange={(e) => setSteps(e.target.value)}
                  placeholder={"u = x**2 + 1\ndu = 2*x dx"}
                />
                <p className="meta" style={{ marginTop: 6 }}>
                  Có bước thì hệ thống chỉ được <strong>bước sai đầu tiên</strong>, thay vì
                  chỉ nói đáp án chưa đúng.
                </p>
              </div>
            ) : (
              <button
                type="button"
                className="ghost small"
                style={{ marginTop: 10 }}
                onClick={() => setShowSteps(true)}
              >
                + Trình bày từng bước (để được chỉ đúng chỗ sai)
              </button>
            )}

            <div className="row" style={{ marginTop: 18 }}>
              <button type="submit" disabled={busy || !answer.trim()}>
                {busy && <span className="spin" aria-hidden="true" />}
                Nộp bài
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => void askHint(false)}
                disabled={busy}
              >
                {hint ? "Gợi ý thêm" : "Xin gợi ý"}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => void nextItem(session)}
                disabled={busy}
              >
                Bài khác
              </button>
            </div>

            {error && <p className="error">{error}</p>}
          </form>
        </>
      ) : (
        <div className="panel">
          <div className="skeleton tall w60" />
          <div className="skeleton" />
          <div className="skeleton w40" />
        </div>
      )}

      {result && <Verdict result={result} onNext={() => session && void nextItem(session)} />}

      {hint && (
        <div className="hint">
          <div className="level">
            <Ladder level={hint.level} />
            Mức {hint.level} · {hint.level_label}
            <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>
              {hint.source === "llm" ? "· do mô hình diễn đạt" : "· mẫu có sẵn"}
            </span>
          </div>
          <div className="text">{hint.text}</div>
          <div className="row tight" style={{ marginTop: 12 }}>
            {hint.level < 4 && (
              <button
                type="button"
                className="secondary small"
                onClick={() => void askHint(false)}
                disabled={busy}
              >
                Vẫn chưa hiểu, gợi ý rõ hơn
              </button>
            )}
            {hint.level >= 4 && hint.level < 5 && (
              <button
                type="button"
                className="secondary small"
                onClick={() => void askHint(true)}
                disabled={busy}
              >
                Cho em xem lời giải đầy đủ
              </button>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

/**
 * Ba trạng thái, không phải hai.
 *
 * ``final_answer_correct === null`` nghĩa là bộ chấm KHÔNG ĐỌC ĐƯỢC bài làm —
 * đó là lỗi định dạng, không phải lỗi toán. Gộp nó vào "sai" là mắng oan người
 * học, và trước đây hệ thống còn trừ cả mức thành thạo vì chuyện đó.
 */
function Verdict({ result, onNext }: { result: AttemptResponse; onNext: () => void }) {
  const unreadable = result.final_answer_correct === null && result.first_wrong_step === null;
  const kind = result.is_correct ? "ok" : unreadable ? "unknown" : "wrong";
  const title = result.is_correct
    ? "Đúng rồi"
    : unreadable
      ? "Chưa đọc được đáp án"
      : "Chưa đúng";

  return (
    <div className={`verdict ${kind}`}>
      <span className="icon" aria-hidden="true">
        {result.is_correct ? "✓" : unreadable ? "?" : "✕"}
      </span>
      <div className="body">
        <strong>{title}</strong>
        <div>{result.message}</div>
        {result.first_wrong_step !== null && (
          <div className="meta" style={{ marginTop: 6 }}>
            Bước sai đầu tiên: bước {result.first_wrong_step}
          </div>
        )}
        {unreadable && (
          <div className="meta" style={{ marginTop: 6 }}>
            Bài làm chưa được tính là sai — mức thành thạo giữ nguyên.
          </div>
        )}
        {result.is_correct && (
          <div className="row" style={{ marginTop: 12 }}>
            <button type="button" onClick={onNext}>
              Bài tiếp theo →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
