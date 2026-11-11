"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Card } from "../../../lib/api";
import { saveSession } from "../../../lib/session";
import { useApp } from "../../providers";
import { MathText } from "../../mathtext";
import { Steps } from "../../steps";

export default function CardPage() {
  const params = useParams<{ skill: string }>();
  const skillId = decodeURIComponent(params.skill);
  const [card, setCard] = useState<Card | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [starting, setStarting] = useState(false);
  const { user, setScope } = useApp();
  const router = useRouter();

  /** Mở trang luyện tập, lọc sẵn đúng kỹ năng của thẻ này. */
  async function practice() {
    if (!card) return;
    if (!user) {
      router.push(`/login?next=${encodeURIComponent(`/library/${card.skill_id}`)}`);
      return;
    }
    setStarting(true);
    try {
      const session = await api.startSession(card.subject);
      saveSession({ sessionId: session.session_id, userId: session.user_id, subject: session.subject });
      setScope({ chapter: card.chapter, skill: card.skill_id, topic: null });
      router.push("/practice");
    } catch (exc) {
      setError((exc as Error).message);
      setStarting(false);
    }
  }

  useEffect(() => {
    api.knowledgeCard(skillId).then(setCard).catch((exc: Error) => setError(exc.message));
  }, [skillId]);

  if (error) return <main><p className="error">{error}</p><Link href="/library">← Thư viện</Link></main>;
  if (!card) return <main><div className="panel"><div className="skeleton tall w60" /><div className="skeleton" /><div className="skeleton" /></div></main>;

  return (
    <main className="card-page">
      <Link className="back-link" href="/library">← Thư viện · {card.subject}</Link>
      <span className="eyebrow">{card.chapter_vi}</span>
      <h1>{card.name_vi}</h1>
      <p className="lead">{card.name_en}</p>

      <div className="card-layout">
        <div>
          <section className="panel">
            <h2 className="panel-title">Kiến thức cần nhớ</h2>
            <ul className="theory">
              {card.theory.map((line) => <li key={line}><MathText text={line} /></li>)}
            </ul>
          </section>

          {card.example && (
            <section className="panel">
              <h2 className="panel-title">Ví dụ giải từng bước</h2>
              <p className="statement"><MathText text={card.example.statement} /></p>
              <Steps steps={card.example.steps} hideLastResult={!showAnswer} />
              {showAnswer ? (
                <p className="answer-line">Đáp án: <strong><MathText text={card.example.answer} /></strong></p>
              ) : (
                <button type="button" className="secondary small" onClick={() => setShowAnswer(true)}>
                  Tự làm bước cuối rồi bấm để đối chiếu đáp án
                </button>
              )}
            </section>
          )}
        </div>

        <aside>
          <section className="panel formula-panel">
            <h2 className="panel-title">Công thức</h2>
            {card.formulas.map((formula) => <div key={formula} className="formula-chip"><MathText text={formula} /></div>)}
          </section>

          {card.mistakes.length > 0 && (
            <section className="panel">
              <h2 className="panel-title">Lỗi hay gặp</h2>
              <ul className="mistakes">
                {card.mistakes.map((m) => (
                  <li key={m.name}>
                    <strong>{m.name}</strong>
                    <span><MathText text={m.description} /></span>
                    <span className="self-check">Tự kiểm: <MathText text={m.self_check} /></span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {(card.methods.length > 0 || card.prerequisites.length > 0) && (
            <section className="panel">
              {card.methods.length > 0 && (
                <>
                  <h2 className="panel-title">Các dạng bài</h2>
                  <div className="chips">{card.methods.map((m) => <span key={m} className="chip">{m}</span>)}</div>
                </>
              )}
              {card.prerequisites.length > 0 && (
                <>
                  <h2 className="panel-title" style={{ marginTop: 16 }}>Nên nắm trước</h2>
                  <div className="chips">{card.prerequisites.map((m) => <span key={m} className="chip accent">{m}</span>)}</div>
                </>
              )}
            </section>
          )}

          <button type="button" className="block start-button" onClick={() => void practice()} disabled={starting}>
            {starting && <span className="spin" aria-hidden="true" />}
            Luyện {card.item_count.toLocaleString("vi-VN")} bài của phần này <span aria-hidden="true">→</span>
          </button>
        </aside>
      </div>
    </main>
  );
}
