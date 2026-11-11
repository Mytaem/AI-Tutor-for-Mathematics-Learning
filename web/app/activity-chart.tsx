"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "../lib/api";

/**
 * Số bài mỗi ngày, 14 ngày gần nhất. Một chuỗi số liệu -> một màu, không chú thích
 * (tiêu đề đã gọi tên). Cột bo 4px ở đầu dữ liệu, cách nhau 2px; rê chuột/chạm vào
 * cột để xem số; có bảng ẩn cho trình đọc màn hình.
 */
export function ActivityChart() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);

  if (!stats) return <div className="panel"><div className="skeleton tall" /></div>;

  const days = stats.last14;
  // Thang luôn chứa cả vạch mục tiêu, để vạch đó nhìn thấy được kể cả ngày ít bài.
  const max = Math.max(stats.daily_goal + 2, ...days.map((d) => d.attempts));
  const W = 560, H = 140, gap = 2;
  const bar = (W - gap * (days.length - 1)) / days.length;
  const label = (iso: string) => {
    const [, m, d] = iso.split("-");
    return `${Number(d)}/${Number(m)}`;
  };
  const shown = active ?? days.length - 1;

  return (
    <section className="panel chart-panel">
      <div className="row spread">
        <h2 className="panel-title" style={{ margin: 0 }}>Số bài mỗi ngày · 14 ngày</h2>
        <span className="meta">
          {label(days[shown].date)}: <strong>{days[shown].attempts}</strong> bài, {days[shown].correct} đúng
        </span>
      </div>
      <div className="chart-meta">
        <span><strong>{stats.streak_days}</strong> ngày liên tiếp</span>
        <span>Hôm nay <strong>{stats.today_attempts}</strong>/{stats.daily_goal} bài</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="activity-chart" role="img"
        aria-label={`Số bài mỗi ngày trong 14 ngày, nhiều nhất ${Math.max(...days.map((d) => d.attempts))} bài`}
        onMouseLeave={() => setActive(null)}>
        <line x1="0" x2={W} y1={H} y2={H} className="chart-axis" vectorEffect="non-scaling-stroke" />
        <line x1="0" x2={W} y1={H - (stats.daily_goal / max) * H} y2={H - (stats.daily_goal / max) * H}
          className="chart-goal" vectorEffect="non-scaling-stroke" />
        {days.map((day, i) => {
          const h = day.attempts ? Math.max(4, (day.attempts / max) * H) : 0;
          const x = i * (bar + gap);
          return (
            <g key={day.date} onMouseEnter={() => setActive(i)} onClick={() => setActive(i)}>
              <rect x={x} y={0} width={bar} height={H} className="chart-hit" />
              {h > 0 && (
                <path className={`chart-bar ${i === shown ? "on" : ""}`}
                  d={`M${x},${H} V${H - h + 4} q0,-4 4,-4 h${bar - 8} q4,0 4,4 V${H} Z`} />
              )}
            </g>
          );
        })}
      </svg>
      {/* Nhãn ngày nằm ngoài SVG: SVG co giãn theo bề ngang, chữ trong đó sẽ méo theo. */}
      <div className="chart-labels" aria-hidden="true">
        {days.map((day, i) => (
          <span key={day.date}>{i % 2 === 1 || i === days.length - 1 ? label(day.date) : ""}</span>
        ))}
      </div>
      <table className="sr-only">
        <caption>Số bài làm và số bài đúng mỗi ngày</caption>
        <thead><tr><th>Ngày</th><th>Số bài</th><th>Đúng</th></tr></thead>
        <tbody>{days.map((d) => <tr key={d.date}><td>{d.date}</td><td>{d.attempts}</td><td>{d.correct}</td></tr>)}</tbody>
      </table>
    </section>
  );
}
