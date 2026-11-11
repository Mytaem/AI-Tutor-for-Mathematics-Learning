"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Stats } from "../lib/api";

/** Vòng tiến độ mục tiêu hôm nay — một con số kèm hình, không cần cả biểu đồ. */
function GoalRing({ done, goal }: { done: number; goal: number }) {
  const ratio = Math.min(1, goal ? done / goal : 0);
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg className="goal-ring" viewBox="0 0 64 64" role="img" aria-label={`${done} trên ${goal} bài hôm nay`}>
      <circle cx="32" cy="32" r={r} className="ring-track" />
      <circle cx="32" cy="32" r={r} className="ring-value" strokeDasharray={`${c * ratio} ${c}`}
        transform="rotate(-90 32 32)" />
      <text x="32" y="36" textAnchor="middle" className="ring-text">{done}/{goal}</text>
    </svg>
  );
}

export function Dashboard({ name, subject, onContinue, busy }: {
  name: string;
  subject: string;
  onContinue: () => void;
  busy: boolean;
}) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);

  const accuracy = stats && stats.total_attempts ? Math.round((stats.total_correct / stats.total_attempts) * 100) : null;
  const goalDone = stats ? stats.today_attempts >= stats.daily_goal : false;

  return (
    <section className="dashboard">
      <div className="dash-hello">
        <span className="eyebrow">Chào {name}</span>
        <h1>{goalDone ? "Đã đạt mục tiêu hôm nay." : "Hôm nay mình học gì nhỉ?"}</h1>
        <p className="lead">
          {stats && stats.streak_days > 1
            ? `Bạn đã học ${stats.streak_days} ngày liên tiếp — giữ chuỗi nhé.`
            : "Mỗi ngày 10 bài là đủ để tiến bộ đều."}
        </p>
        <div className="row">
          <button type="button" className="start-button" onClick={onContinue} disabled={busy || !subject}>
            {busy && <span className="spin" aria-hidden="true" />}
            Tiếp tục luyện {subject} <span aria-hidden="true">→</span>
          </button>
          <Link className="button secondary-link" href={`/practice?mode=review&subject=${subject}`}>Ôn lỗi sai</Link>
        </div>
      </div>

      <div className="dash-stats">
        <div className="stat-tile goal">
          {stats ? <GoalRing done={stats.today_attempts} goal={stats.daily_goal} /> : <div className="skeleton ring" />}
          <span className="stat-label">Mục tiêu hôm nay</span>
        </div>
        <div className="stat-tile">
          <span className="stat-value">{stats ? stats.streak_days : "–"}</span>
          <span className="stat-label">ngày học liên tiếp</span>
        </div>
        <div className="stat-tile">
          <span className="stat-value">{accuracy === null ? "–" : `${accuracy}%`}</span>
          <span className="stat-label">trả lời đúng · {stats?.total_attempts ?? 0} bài</span>
        </div>
      </div>

      <nav className="quick-links" aria-label="Lối tắt">
        <Link href="/library"><strong>Thư viện kiến thức</strong><span>70 thẻ công thức và ví dụ giải</span></Link>
        <Link href="/ask"><strong>Hỏi đáp</strong><span>Hỏi lý thuyết, có dẫn nguồn</span></Link>
        <Link href="/history"><strong>Lịch sử</strong><span>Xem lại bài đã làm</span></Link>
        <Link href="/progress"><strong>Tiến độ</strong><span>Mức thành thạo từng kỹ năng</span></Link>
      </nav>
    </section>
  );
}
