"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import katex from "katex";
import { api, type AttemptResponse, type Hint, type ItemSolution, type PublicItem } from "../../lib/api";
import { loadSession, saveSession, type StoredSession } from "../../lib/session";
import type { Scope } from "../../lib/prefs";
import { ApiDownBanner } from "../api-status";
import { useApp } from "../providers";
import { MathText } from "../mathtext";
import { ScopeLine } from "../scope-picker";
import { HintText, Steps } from "../steps";

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

  const colon = item.statement_vi.indexOf(":");
  const words = html && colon > 0 ? item.statement_vi.slice(0, colon + 1) : item.statement_vi;
  return (
    <>
      <p className="statement"><MathText text={words} /></p>
      {html && <div className="statement-math" dangerouslySetInnerHTML={{ __html: html }} />}
    </>
  );
}

const ANSWER_HELP: Record<string, string> = {
  expression: "Biểu thức, ví dụ x**2/2 + C",
  antiderivative: "Nguyên hàm, nhớ + C",
  number: "Nhập số thập phân hoặc phân số",
  set: "Các phần tử cách nhau bởi dấu phẩy: 1, 3",
  matrix: "Ma trận [[1, 2], [3, 4]] hoặc vector [1, 2]",
  eigenvector: "Ví dụ: [1, 2]",
  linear_system: "Ví dụ: [2, 1] hoặc x = 2, y = 1",
  ode_solution: "Nghiệm kèm hằng số tự do, ví dụ C1*exp(x)",
  boolean: "Trả lời có / không",
  text: "Trả lời bằng lời",
};

const HINT_SOURCE: Record<string, string> = {
  solution: "· theo lời giải đã kiểm chứng",
  taxonomy: "· theo đúng lỗi em vừa mắc",
  reference: "· theo lời giải mẫu",
  llm: "· do mô hình diễn đạt",
  template: "· gợi ý chung",
  fallback: "· gợi ý an toàn",
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
  const { scope, ready, user } = useApp();
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
  // Lời giải đầy đủ phải xin HAI lần (chính sách gợi ý). Lần đầu không ra gì thì
  // người học tưởng nút hỏng — nên phải nói rõ là cần xác nhận.
  const [solutionAsked, setSolutionAsked] = useState(false);
  const [solution, setSolution] = useState<ItemSolution | null>(null);
  // Ôn lỗi sai: /practice?mode=review&subject=MAS291 — lấy lại bài từng làm sai.
  const [review, setReview] = useState(false);
  const answerBox = useRef<HTMLInputElement>(null);

  // `within` truyền tường minh chứ không lấy từ closure: để deps rỗng mà vẫn
  // đọc `scope` thì hàm này giữ mãi phạm vi của lần vẽ đầu, và đổi chương ở
  // cột phải sẽ không có tác dụng gì.
  const nextItem = useCallback(async (current: StoredSession, within: Scope, reviewing = false) => {
    setBusy(true);
    setError(null);
    try {
      const next = reviewing ? await api.reviewItem(current.subject) : await api.nextItem(current.subject, within);
      setItem(next);
      setAnswer("");
      setSteps("");
      setShowSteps(false);
      setResult(null);
      setHint(null);
      setSolutionAsked(false);
      setSolution(null);
      setDown(false);
      // Con trỏ nhảy thẳng vào ô đáp án: luyện tập là gõ liên tục, bắt người
      // học với chuột sau mỗi bài là chỗ rò thời gian lớn nhất của màn hình này.
      window.setTimeout(() => answerBox.current?.focus(), 30);
    } catch (exc) {
      setItem(null);
      setError((exc as Error).message);
      // Hết bài sai để ôn là tin vui, không phải sự cố kết nối.
      setDown(!reviewing);
    } finally {
      setBusy(false);
    }
  }, []);

  // Chờ `ready` mới gọi: chưa đọc xong localStorage thì `scope` còn rỗng, gọi
  // luôn sẽ lấy một đề ngoài phạm vi rồi đổi ngay — người học thấy đề nhảy một
  // nhịp và hệ thống tốn một lượt gọi vô ích.
  //
  // `scope` nằm trong deps là CỐ Ý: đổi chương ở cột phải thì đổi luôn sang đề
  // của chương đó, không phải bấm thêm "Bài khác".
  useEffect(() => {
    if (!ready || !user) return;
    const params = new URLSearchParams(window.location.search);
    const reviewing = params.get("mode") === "review";
    const wanted = params.get("subject");
    setReview(reviewing);
    let saved = loadSession();
    if (saved && saved.userId !== user.user_id) saved = null;     // phiên của tài khoản khác
    const start = async () => {
      // Vào ôn lỗi sai của một môn khác môn đang học: mở phiên mới cho môn đó.
      if (wanted && (!saved || saved.subject !== wanted)) {
        const fresh = await api.startSession(wanted);
        saved = { sessionId: fresh.session_id, userId: fresh.user_id, subject: fresh.subject };
        saveSession(saved);
      }
      if (!saved) {
        router.push("/");
        return;
      }
      setSession(saved);
      void nextItem(saved, scope, reviewing);
    };
    start().catch((exc: Error) => setError(exc.message));
  }, [ready, user, scope, router, nextItem]);

  async function showSolution() {
    if (!item) return;
    try {
      setSolution(await api.solution(item.item_id));
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

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
      const next = await api.hint(session.sessionId, item.item_id, solution);
      setHint(next);
      setSolutionAsked(solution && next.level < 5);
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
          <span className="eyebrow">{session.subject}</span>
          <h1 style={{ marginBottom: 2 }}>Luyện tập</h1>
          <div className="meta">
            {user?.display_name}{solved > 0 && ` · ${solved} bài đúng`}
          </div>
        </div>
        <button type="button" className="ghost small" onClick={() => router.push("/progress")}>
          Xem tiến độ →
        </button>
      </div>

      {review && (
        <div className="mode-banner">
          <span><strong>Ôn lỗi sai</strong> — các bài bạn từng làm sai, bài cũ nhất trước.</span>
          <button type="button" className="ghost small" onClick={() => {
            window.history.replaceState(null, "", "/practice");
            setReview(false);
            if (session) void nextItem(session, scope, false);
          }}>Thoát chế độ ôn</button>
        </div>
      )}

      {down && <ApiDownBanner />}

      <ScopeLine subject={session.subject} />

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
              {item.chapter_vi && <span className="chip">Chương: {item.chapter_vi}</span>}
              {item.skill_names.length > 0 && item.skill_names.join(" · ") !== item.chapter_vi && (
                <span className="chip accent">{item.skill_names.join(" · ")}</span>
              )}
              <span className="chip">Độ khó: {DIFFICULTY(item.difficulty)}</span>
            </div>
            <div className="panel-body">
              <Statement item={item} />
              {/* Mã đề để khi người học báo lỗi, người hỗ trợ tra được đúng đề. */}
              <p className="meta" style={{ marginTop: 12, marginBottom: 0 }}>
                {item.topic_vi && <>Dạng bài: {item.topic_vi} · </>}
                Mã đề <span className="mono">{item.item_id}</span>
              </p>
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
                <label htmlFor="steps">Các bước làm</label>
                <textarea
                  id="steps"
                  value={steps}
                  onChange={(e) => setSteps(e.target.value)}
                  placeholder={"u = x**2 + 1\ndu = 2*x dx"}
                />
                <p className="meta" style={{ marginTop: 6 }}>Mỗi dòng một bước.</p>
              </div>
            ) : (
              <button
                type="button"
                className="ghost small"
                style={{ marginTop: 10 }}
                onClick={() => setShowSteps(true)}
              >
                + Thêm các bước làm
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
                onClick={() => void nextItem(session, scope)}
                disabled={busy}
              >
                Bài khác
              </button>
            </div>

            {error && <p className="error">{error}</p>}
          </form>
        </>
      ) : error ? (
        /* Không có đề trong phạm vi đã chọn. Phải nói ra, chứ để khung chờ
           quay mãi thì người học tưởng hệ thống treo. */
        <div className="panel empty">
          <p>{error}</p>
          <p className="meta">{review ? "Thoát chế độ ôn để luyện bài mới." : "Đổi phạm vi hoặc bỏ bộ lọc để tiếp tục."}</p>
        </div>
      ) : (
        <div className="panel">
          <div className="skeleton tall w60" />
          <div className="skeleton" />
          <div className="skeleton w40" />
        </div>
      )}

      {result && (
        <Verdict
          result={result}
          onNext={() => session && void nextItem(session, scope, review)}
          onSolution={solution ? undefined : () => void showSolution()}
        />
      )}

      {solution && (
        <section className="panel solution-panel">
          <h2 className="panel-title">Lời giải mẫu</h2>
          <p className="meta">{solution.theory}</p>
          <Steps steps={solution.steps} />
          <p className="answer-line">Đáp án: <strong><MathText text={solution.answer} /></strong></p>
        </section>
      )}

      {hint && (
        <div className="hint">
          <div className="level">
            <Ladder level={hint.level} />
            Mức {hint.level} · {hint.level_label}
            <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>
              {HINT_SOURCE[hint.source] ?? ""}
            </span>
          </div>
          <div className="text">
            <HintText text={hint.text} />
          </div>
          <div className="row tight" style={{ marginTop: 12 }}>
            {hint.level < 4 && (
              <button
                type="button"
                className="secondary small"
                onClick={() => void askHint(false)}
                disabled={busy}
              >
                Gợi ý rõ hơn
              </button>
            )}
            {hint.level >= 4 && hint.level < 5 && (
              <>
                {solutionAsked && (
                  <p className="meta" style={{ margin: 0, flexBasis: "100%" }}>
                    Em thử tự làm phép tính ở bước cuối trước nhé — chỉ còn một bước. Vẫn muốn xem
                    lời giải thì bấm lần nữa.
                  </p>
                )}
                <button
                  type="button"
                  className="secondary small"
                  onClick={() => void askHint(true)}
                  disabled={busy}
                >
                  {solutionAsked ? "Vẫn xem lời giải" : "Xem lời giải"}
                </button>
              </>
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
function Verdict({ result, onNext, onSolution }: {
  result: AttemptResponse;
  onNext: () => void;
  onSolution?: () => void;
}) {
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
            {onSolution && (
              <button type="button" className="secondary" onClick={onSolution}>
                Xem lời giải mẫu
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
