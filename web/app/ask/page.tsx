"use client";

import { useEffect, useState } from "react";
import { api, type AskResponse, type Card } from "../../lib/api";
import { loadSession } from "../../lib/session";
import { ApiDownBanner } from "../api-status";
import { useApp } from "../providers";
import { HintText } from "../steps";
import Link from "next/link";
import { MathText } from "../mathtext";
import { ScopeLine } from "../scope-picker";

const EXAMPLES = [
  "Chu trình Euler là gì?",
  "Khi nào dùng kiểm định t thay vì z?",
  "Ma trận nghịch đảo tính thế nào?",
  "Tích phân từng phần dùng khi nào?",
];

export default function AskPage() {
  const { scope } = useApp();
  const [subject, setSubject] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cards, setCards] = useState<Card[]>([]);

  useEffect(() => {
    setSubject(loadSession()?.subject ?? null);
  }, []);

  async function ask(text: string) {
    if (!text.trim()) return;
    setQuestion(text);
    setAsked(text.trim());
    setBusy(true);
    setError(null);
    setAnswer(null);
    setCards([]);
    // Thẻ kiến thức về ngay (không cần model) — người hỏi có cái để đọc trong lúc chờ.
    api.knowledgeMatch(text.trim(), subject).then(setCards).catch(() => setCards([]));
    try {
      // Chọn chương thì thu hẹp truy xuất về đúng chương đó. Không chọn môn
      // thì để server tìm trên cả kho — hỏi lý thuyết phải dùng được ngay,
      // không bắt tạo phiên trước.
      setAnswer(await api.ask(text.trim(), subject ?? undefined, scope.chapter));
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
      <span className="eyebrow">Hỏi đáp lý thuyết</span>
      <h1>Hỏi gì cũng được, miễn trong môn học</h1>
      <p className="lead">
        Câu trả lời dựa trên giáo trình và thẻ kiến thức đã kiểm chứng, mỗi ý đều ghi nguồn. Không có trong
        tài liệu thì hệ thống nói thẳng, không đoán.
      </p>

      {down && <ApiDownBanner />}

      <ScopeLine subject={subject} />

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
            placeholder="Định lý giới hạn trung tâm nói gì?"
            autoComplete="off"
            style={{ flex: "1 1 240px" }}
          />
          <button type="submit" disabled={busy || !question.trim()}>
            {busy && <span className="spin" aria-hidden="true" />}
            {busy ? "Đang tra…" : "Hỏi"}
          </button>
        </div>

        <p className="meta" style={{ margin: "14px 0 7px" }}>Gợi ý câu hỏi</p>
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

        {error && <p className="error">{error}</p>}
      </form>

      {cards.length > 0 && (
        <section className="quick-cards" aria-label="Thẻ kiến thức liên quan">
          {cards.map((card) => (
            <article key={card.skill_id} className="quick-card">
              <div className="quick-card-head">
                <span className="eyebrow">Thẻ kiến thức · {card.chapter_vi}</span>
                <Link href={`/library/${encodeURIComponent(card.skill_id)}`} className="meta">Xem đầy đủ →</Link>
              </div>
              <h3>{card.name_vi}</h3>
              <p><MathText text={card.theory[0] ?? ""} /></p>
              <div className="chips">
                {card.formulas.slice(0, 2).map((f) => <span key={f} className="formula-chip"><MathText text={f} /></span>)}
              </div>
            </article>
          ))}
        </section>
      )}

      {busy && (
        <div className="panel" aria-live="polite">
          <p className="meta" style={{ marginTop: 0 }}>
            Đang tra giáo trình và soạn câu trả lời — thường mất 20–60 giây.
          </p>
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
              <span className="meta">“{asked}”</span>
            </div>
            <div className="answer-body">
              <HintText text={answer.answer} />
            </div>
            <p className="meta" style={{ marginTop: 14 }}>Nội dung được tổng hợp từ các nguồn bên dưới.</p>
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
