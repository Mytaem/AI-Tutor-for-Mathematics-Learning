"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Progress } from "../../lib/api";
import { loadSession } from "../../lib/session";

/** Đổi mức thành thạo thành một câu người học hiểu được, không chỉ là con số. */
function label(mastery: number): string {
  if (mastery >= 0.85) return "đã vững";
  if (mastery >= 0.6) return "gần vững";
  if (mastery >= 0.35) return "đang học";
  return "còn yếu";
}

export default function ProgressPage() {
  const router = useRouter();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);

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
      .catch((exc: Error) => setError(exc.message));
  }, [router]);

  if (error) return <main><p className="error">{error}</p></main>;
  if (!progress) return <main><p>Đang tải…</p></main>;

  const sorted = [...progress.skills].sort((a, b) => a.mastery - b.mastery);
  const accuracy = progress.attempts ? progress.correct / progress.attempts : 0;

  return (
    <main>
      <h1>Tiến độ — {subject}</h1>
      <p className="lead">
        {progress.attempts} lượt làm bài, đúng {progress.correct} ({(accuracy * 100).toFixed(0)}%).
        Mức thành thạo do mô hình BKT ước lượng từ chính các lượt làm bài, không phải
        điểm trung bình.
      </p>

      <h2>Kỹ năng cần luyện trước</h2>
      <div className="panel">
        <table>
          <tbody>
            {sorted.map((skill) => (
              <tr key={skill.skill_id}>
                <td className="name">
                  {skill.name_vi}
                  <div className="meta">{skill.skill_id}</div>
                </td>
                <td>
                  <div className="bar">
                    <span style={{ width: `${Math.round(skill.mastery * 100)}%` }} />
                  </div>
                </td>
                <td className="value">{(skill.mastery * 100).toFixed(0)}%</td>
                <td className="value">{label(skill.mastery)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
