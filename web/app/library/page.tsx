"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type CardSummary } from "../../lib/api";
import { loadSession } from "../../lib/session";
import { MathText } from "../mathtext";

const SUBJECTS = [
  { code: "MAE101", name: "Toán cho kỹ thuật" },
  { code: "MAD101", name: "Toán rời rạc" },
  { code: "MAI391", name: "Toán cho học máy" },
  { code: "MAS291", name: "Xác suất và thống kê" },
];

function fold(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").toLowerCase();
}

export default function LibraryPage() {
  const [subject, setSubject] = useState("MAE101");
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = loadSession()?.subject;
    if (saved) setSubject(saved);
  }, []);

  useEffect(() => {
    setCards(null);
    setError(null);
    api.knowledge(subject).then(setCards).catch((exc: Error) => setError(exc.message));
  }, [subject]);

  const chapters = useMemo(() => {
    const needle = fold(query.trim());
    const groups = new Map<string, CardSummary[]>();
    for (const card of cards ?? []) {
      if (needle && !fold(`${card.name_vi} ${card.name_en} ${card.formula}`).includes(needle)) continue;
      groups.set(card.chapter_vi, [...(groups.get(card.chapter_vi) ?? []), card]);
    }
    return [...groups.entries()];
  }, [cards, query]);

  return (
    <main>
      <span className="eyebrow">Thư viện kiến thức</span>
      <h1>Công thức và cách làm, theo từng bài</h1>
      <p className="lead">
        Mỗi thẻ gồm lý thuyết, công thức, lỗi hay gặp và một ví dụ giải từng bước. Lời giải do máy tính và
        được bộ chấm kiểm lại, nên khớp đúng với cách hệ thống chấm bài của bạn.
      </p>

      <div className="library-tools">
        <div className="seg subject-tabs" role="tablist" aria-label="Chọn môn">
          {SUBJECTS.map((s) => (
            <button key={s.code} type="button" role="tab" aria-selected={subject === s.code}
              aria-pressed={subject === s.code} onClick={() => setSubject(s.code)}>
              <strong>{s.code}</strong><span className="tab-sub">{s.name}</span>
            </button>
          ))}
        </div>
        <input type="text" className="search" placeholder="Tìm: tích phân từng phần, bayes, ma trận…"
          value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Tìm thẻ kiến thức" />
      </div>

      {error && <p className="error">{error}</p>}
      {!cards && !error && (
        <div className="card-grid">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="kcard"><div className="skeleton tall" /><div className="skeleton" /></div>)}</div>
      )}
      {cards && chapters.length === 0 && <div className="panel empty"><p>Không có thẻ nào khớp “{query}”.</p></div>}

      {chapters.map(([chapter, group]) => (
        <section key={chapter}>
          <h2 className="chapter-title">{chapter}</h2>
          <div className="card-grid">
            {group.map((card) => (
              <Link key={card.skill_id} href={`/library/${encodeURIComponent(card.skill_id)}`} className="kcard">
                <span className="kcard-name">{card.name_vi}</span>
                <span className="kcard-en">{card.name_en}</span>
                {card.formula && <span className="kcard-formula"><MathText text={card.formula} /></span>}
                <span className="kcard-meta">{card.item_count.toLocaleString("vi-VN")} bài luyện <span aria-hidden="true">→</span></span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
