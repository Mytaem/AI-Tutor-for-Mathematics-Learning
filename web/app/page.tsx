"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { loadSession, saveSession } from "../lib/session";
import { ApiDownBanner } from "./api-status";
import { EMPTY_SCOPE } from "../lib/prefs";
import { useApp } from "./providers";
import { Dashboard } from "./dashboard";

const SUBJECTS: Record<string, { name: string; topics: string }> = {
  MAE101: {
    name: "Toán cho kỹ thuật",
    topics: "Giới hạn · Đạo hàm · Tích phân · Đại số tuyến tính",
  },
  MAD101: {
    name: "Toán rời rạc",
    topics: "Logic · Tổ hợp · Truy hồi · Đồ thị",
  },
  MAI391: {
    name: "Toán cho học máy",
    topics: "Ma trận · Trị riêng · Chéo hoá · Chuẩn vector",
  },
  MAS291: {
    name: "Xác suất và thống kê",
    topics: "Xác suất · Phân phối · Ước lượng · Kiểm định",
  },
};

type Health = { subjects: Record<string, { items: number; skills: number }> };

export default function HomePage() {
  const router = useRouter();
  const { setScope, user } = useApp();
  const [subjects, setSubjects] = useState<string[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.subjects(), api.health() as Promise<unknown>])
      .then(([list, info]) => {
        setSubjects(list);
        setHealth(info as Health);
        setSubject((current) => current || list[0] || "");
        setDown(false);
      })
      .catch(() => setDown(true));

    const saved = loadSession();
    if (saved) setSubject(saved.subject);
  }, []);

  async function start(event?: React.FormEvent) {
    event?.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const session = await api.startSession(subject);
      saveSession({
        sessionId: session.session_id,
        userId: session.user_id,
        subject: session.subject,
      });
      setScope(EMPTY_SCOPE);
      router.push("/practice");
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = Boolean(subject) && Boolean(user);

  return (
    <main>
      {user ? (
        <Dashboard name={user.display_name} subject={subject} busy={busy} onContinue={() => void start()} />
      ) : (
        <section className="welcome">
          <div>
            <span className="eyebrow">Gia sư toán cho sinh viên</span>
            <h1>Làm sai ở bước nào, biết ngay bước đó.</h1>
            <p className="lead">
              4.955 bài luyện có lời giải từng bước được máy kiểm chứng. Gợi ý đi từ công thức tới
              từng bước — không đưa đáp án ngay, để bạn tự làm được.
            </p>
            <ul className="welcome-points">
              <li>Hiểu cách bạn viết: x², sinx, căn x, 0,75</li>
              <li>Gợi ý 6 mức, đúng chỗ bạn sai</li>
              <li>Thư viện 70 thẻ công thức và ví dụ</li>
            </ul>
          </div>
          <div className="welcome-mark" aria-hidden="true">∑</div>
        </section>
      )}

      {down && <ApiDownBanner />}

      <form onSubmit={start} className={`start-layout${user ? " solo" : ""}`}>
        <section>
          <div className="section-heading">
            <div><span className="step">01</span><h2>Chọn học phần</h2></div>
            <span className="meta">{subjects.length || 4} học phần</span>
          </div>
          <div className="cards">
            {subjects.map((code, index) => {
              const info = SUBJECTS[code] ?? { name: code, topics: "" };
              const stat = health?.subjects?.[code];
              return (
                <button type="button" key={code} className={`card course-${index + 1}`} aria-pressed={subject === code} onClick={() => setSubject(code)}>
                  <span className="course-icon" aria-hidden="true">{["∫", "◇", "λ", "σ"][index] ?? "∑"}</span>
                  <span className="course-copy">
                    <span className="code">{code}</span>
                    <span className="desc">{info.name}</span>
                    <span className="meta course-topics">{info.topics}</span>
                    {stat && <span className="course-stat">{stat.items.toLocaleString("vi-VN")} bài · {stat.skills} kỹ năng</span>}
                  </span>
                  <span className="select-indicator" aria-hidden="true">✓</span>
                </button>
              );
            })}
            {subjects.length === 0 && !down && <><div className="card"><div className="skeleton tall w40" /><div className="skeleton" /></div><div className="card"><div className="skeleton tall w40" /><div className="skeleton" /></div></>}
          </div>
        </section>

        {/* Đã đăng nhập thì nút "Tiếp tục luyện" ở bảng trên làm việc này rồi. */}
        <section className="start-panel" hidden={Boolean(user)}>
          <span className="step">02</span>
          <h2>Bắt đầu học</h2>
          {user === undefined ? (
            <div className="skeleton tall" style={{ marginTop: 22 }} />
          ) : user ? (
            <>
              <p className="meta">Xin chào <strong>{user.display_name}</strong> — tiến độ được lưu vào tài khoản của bạn.</p>
              <button type="submit" className="block start-button" disabled={busy || !ready}>
                {busy && <span className="spin" aria-hidden="true" />}
                {busy ? "Đang chuẩn bị…" : "Bắt đầu luyện"}
                {!busy && <span aria-hidden="true">→</span>}
              </button>
            </>
          ) : (
            <>
              <p className="meta">Tạo tài khoản miễn phí để lưu tiến độ và học tiếp trên mọi thiết bị.</p>
              <Link className="button block start-button" href="/login?mode=register&next=/">
                Tạo tài khoản <span aria-hidden="true">→</span>
              </Link>
              <p className="privacy-note">
                Đã có tài khoản? <Link href="/login?next=/">Đăng nhập</Link>
              </p>
            </>
          )}
          {error && <p className="error">{error}</p>}
        </section>
      </form>
    </main>
  );
}
