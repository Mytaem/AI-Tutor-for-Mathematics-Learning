"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type HistoryRow } from "../../lib/api";
import { when } from "../../lib/format";
import { MathText } from "../mathtext";
import { useApp } from "../providers";

const VERDICT: Record<HistoryRow["verdict"], { label: string; cls: string }> = {
  correct: { label: "Đúng", cls: "ok" },
  wrong: { label: "Sai", cls: "wrong" },
  unreadable: { label: "Chưa đọc được", cls: "warn" },
};

export default function HistoryPage() {
  const { user } = useApp();
  const [onlyWrong, setOnlyWrong] = useState(false);
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setRows(null);
    api.history(onlyWrong).then(setRows).catch((exc: Error) => setError(exc.message));
  }, [user, onlyWrong]);

  const wrongSubjects = [...new Set((rows ?? []).filter((r) => r.verdict === "wrong").map((r) => r.subject))];

  return (
    <main>
      <span className="eyebrow">Lịch sử làm bài</span>
      <h1>Bạn đã làm những gì</h1>
      <p className="lead">Xem lại từng bài, và ôn đúng những bài còn làm sai — học từ lỗi là cách nhớ lâu nhất.</p>

      <div className="row spread" style={{ marginBottom: 14 }}>
        <div className="seg" role="group" aria-label="Lọc">
          <button type="button" aria-pressed={!onlyWrong} onClick={() => setOnlyWrong(false)}>Tất cả</button>
          <button type="button" aria-pressed={onlyWrong} onClick={() => setOnlyWrong(true)}>Chỉ bài sai</button>
        </div>
        {wrongSubjects.length > 0 && (
          <div className="row tight">
            {wrongSubjects.map((code) => (
              <Link key={code} className="button small" href={`/practice?mode=review&subject=${code}`}>
                Ôn lỗi sai {code}
              </Link>
            ))}
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {!rows && !error && <div className="panel"><div className="skeleton" /><div className="skeleton" /><div className="skeleton w60" /></div>}
      {rows && rows.length === 0 && (
        <div className="panel empty">
          <p>{onlyWrong ? "Chưa có bài sai nào. Tiếp tục giữ phong độ nhé!" : "Bạn chưa làm bài nào."}</p>
          <Link className="button small" href="/">Bắt đầu luyện</Link>
        </div>
      )}

      {rows && rows.length > 0 && (
        <ul className="history">
          {rows.map((row, index) => {
            const verdict = VERDICT[row.verdict];
            return (
              <li key={`${row.item_id}-${index}`} className={`history-row ${verdict.cls}`}>
                <div className="history-main">
                  <div className="history-head">
                    <span className={`chip ${verdict.cls}`}>{verdict.label}</span>
                    <span className="meta">{row.subject} · {row.skill_names.join(" · ")} · {when(row.created_at)}</span>
                  </div>
                  <div className="history-statement"><MathText text={row.statement} /></div>
                  <div className="meta">
                    Bạn trả lời: <span className="mono">{row.answer || "(trống)"}</span>
                    {row.errors.length > 0 && <> · Lỗi: {row.errors.join(", ")}</>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
