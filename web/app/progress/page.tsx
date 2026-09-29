"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Progress, type SkillProgress } from "../../lib/api";
import { loadSession } from "../../lib/session";
import { ApiDownBanner } from "../api-status";

/** Đổi mức thành thạo thành một câu người học hiểu được, không chỉ là con số. */
function band(mastery: number): { label: string; cls: string; chip: string } {
  if (mastery >= 0.85) return { label: "đã vững", cls: "high", chip: "ok" };
  if (mastery >= 0.6) return { label: "gần vững", cls: "high", chip: "ok" };
  if (mastery >= 0.35) return { label: "đang học", cls: "mid", chip: "warn" };
  return { label: "còn yếu", cls: "low", chip: "wrong" };
}

export default function ProgressPage() {
  const router = useRouter();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    const saved = loadSession();
    if (!saved) {
      router.push("/");
      return;
    }
    setSubject(saved.subject);
    api
      .progress(saved.userId, saved.subject)
      .then(setProgress)
      .catch((exc: Error) => {
        setError(exc.message);
        setDown(true);
      });
  }, [router]);

  if (down) {
    return (
      <main>
        <h1>Tiến độ</h1>
        <ApiDownBanner />
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  if (!progress) {
    return (
      <main>
        <h1>Tiến độ</h1>
        <div className="tiles">
          <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
          <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
          <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
        </div>
        <div className="panel"><div className="skeleton" /><div className="skeleton" /><div className="skeleton w60" /></div>
      </main>
    );
  }

  const sorted = [...progress.skills].sort((a, b) => a.mastery - b.mastery);
  const accuracy = progress.attempts ? progress.correct / progress.attempts : 0;
  const solid = progress.skills.filter((s) => s.mastery >= 0.6).length;
  const weak = sorted.filter((s) => s.mastery < 0.35);

  return (
    <main>
      <h1>Tiến độ — {subject}</h1>
      <p className="lead">
        Mức thành thạo do mô hình BKT ước lượng từ chính các lượt làm bài, <strong>không
        phải điểm trung bình</strong>: làm đúng một bài dễ khi đang yếu thì tăng ít, làm
        đúng bài khó thì tăng nhiều.
      </p>

      {progress.attempts === 0 ? (
        <div className="panel empty">
          <p>Chưa có lượt làm bài nào để ước lượng.</p>
          <button type="button" onClick={() => router.push("/practice")} style={{ marginTop: 10 }}>
            Vào luyện tập
          </button>
        </div>
      ) : (
        <>
          <div className="tiles">
            <div className="tile">
              <div className="n">{progress.attempts}</div>
              <div className="k">lượt làm bài</div>
            </div>
            <div className="tile">
              <div className="n">{(accuracy * 100).toFixed(0)}%</div>
              <div className="k">tỉ lệ đúng ({progress.correct} bài)</div>
            </div>
            <div className="tile">
              <div className="n">
                {solid}
                <span style={{ fontSize: "0.9rem", color: "var(--muted)", fontWeight: 400 }}>
                  /{progress.skills.length}
                </span>
              </div>
              <div className="k">kỹ năng từ mức gần vững</div>
            </div>
          </div>

          {weak.length > 0 && (
            <>
              <h2>Nên luyện trước</h2>
              <div className="panel">
                <div className="row tight">
                  {weak.slice(0, 6).map((skill) => (
                    <span className="chip wrong" key={skill.skill_id}>
                      {skill.name_vi}
                    </span>
                  ))}
                </div>
                <p className="meta" style={{ marginTop: 12 }}>
                  Bộ chọn bài không nhất thiết đưa ngay bài khó nhất trong nhóm này — nó
                  chọn bài có xác suất làm đúng quanh 75%, tức vừa đủ sức để học được.
                </p>
              </div>
            </>
          )}

          <h2>Toàn bộ kỹ năng của môn</h2>
          <div className="panel flush">
            <div className="panel-body">
              <table>
                <thead>
                  <tr>
                    <th>Kỹ năng</th>
                    <th>Mức thành thạo</th>
                    <th />
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((skill) => (
                    <Row key={skill.skill_id} skill={skill} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </main>
  );
}

function Row({ skill }: { skill: SkillProgress }) {
  const b = band(skill.mastery);
  return (
    <tr>
      <td className="name">
        {skill.name_vi}
        <div className="meta mono">{skill.skill_id}</div>
      </td>
      <td>
        <div className="bar">
          <span className={b.cls} style={{ width: `${Math.max(2, Math.round(skill.mastery * 100))}%` }} />
        </div>
      </td>
      <td className="value">{(skill.mastery * 100).toFixed(0)}%</td>
      <td className="value">
        <span className={`chip ${b.chip}`}>{b.label}</span>
      </td>
    </tr>
  );
}
