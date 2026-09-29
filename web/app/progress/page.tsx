"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Progress, type SkillProgress } from "../../lib/api";
import { loadSession } from "../../lib/session";
import { ApiDownBanner } from "../api-status";

/**
 * Bốn mức xếp loại, và chúng được in ra thành chú giải ngay trên bảng.
 *
 * Con số 68% một mình không nói cho người học biết nên làm gì tiếp. Mốc chia
 * thì phải hiện ra chứ không giấu trong code — nếu không, hai người đọc cùng
 * một bảng sẽ hiểu "đang học" theo hai nghĩa khác nhau.
 */
const BANDS = [
  { min: 0.85, label: "đã vững", range: "≥ 85%", cls: "high", chip: "ok" },
  { min: 0.6, label: "gần vững", range: "60–85%", cls: "high", chip: "ok" },
  { min: 0.35, label: "đang học", range: "35–60%", cls: "mid", chip: "warn" },
  { min: 0, label: "còn yếu", range: "< 35%", cls: "low", chip: "wrong" },
];

/** Đổi mức thành thạo thành một câu người học hiểu được, không chỉ là con số. */
function band(mastery: number) {
  return BANDS.find((b) => mastery >= b.min) ?? BANDS[BANDS.length - 1];
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
              <div className="k">Lượt làm bài</div>
            </div>
            <div className="tile">
              <div className="n">{(accuracy * 100).toFixed(0)}%</div>
              <div className="k">Tỉ lệ làm đúng — {progress.correct}/{progress.attempts} lượt</div>
            </div>
            <div className="tile">
              <div className="n">
                {solid}
                <span style={{ fontSize: "0.9rem", color: "var(--muted)", fontWeight: 400 }}>
                  /{progress.skills.length}
                </span>
              </div>
              <div className="k">Kỹ năng đạt từ 60% trở lên</div>
            </div>
            <div className="tile">
              <div className="n">{weak.length}</div>
              <div className="k">Kỹ năng còn dưới 35%</div>
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
            <div className="panel-head" style={{ justifyContent: "space-between" }}>
              <span className="meta">Xếp từ kỹ năng yếu nhất lên</span>
              <span className="row tight">
                {BANDS.map((b) => (
                  <span className={`chip ${b.chip}`} key={b.label}>
                    {b.label} {b.range}
                  </span>
                ))}
              </span>
            </div>
            <div className="panel-body">
              <table>
                <caption className="sr-only">
                  Mức thành thạo từng kỹ năng của môn, do mô hình BKT ước lượng
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Kỹ năng</th>
                    <th scope="col">Mức thành thạo (BKT)</th>
                    <th scope="col" style={{ textAlign: "right" }}>
                      Xếp loại
                    </th>
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
  const percent = Math.round(skill.mastery * 100);
  return (
    <tr>
      <th scope="row" className="name" style={{ fontWeight: 400, padding: "10px 8px", textTransform: "none", letterSpacing: 0, fontSize: "0.92rem", color: "var(--ink)" }}>
        {skill.name_vi}
        <div className="meta mono">{skill.skill_id}</div>
      </th>
      {/* Thanh và con số nằm CÙNG một cột: chúng là một đại lượng, tách ra hai
          cột thì cột nào cũng phải có tên riêng mà thật ra không có tên riêng. */}
      <td>
        <div className="row" style={{ gap: 10, flexWrap: "nowrap" }}>
          <div className="bar" style={{ flex: 1, minWidth: 80 }}>
            <span className={b.cls} style={{ width: `${Math.max(2, percent)}%` }} />
          </div>
          <span className="value" style={{ width: 42 }}>{percent}%</span>
        </div>
      </td>
      <td style={{ textAlign: "right" }}>
        <span className={`chip ${b.chip}`}>{b.label}</span>
      </td>
    </tr>
  );
}
