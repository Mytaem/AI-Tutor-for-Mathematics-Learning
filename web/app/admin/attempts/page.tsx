"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type AttemptRow } from "../../../lib/api";
import { when } from "../../../lib/format";
import { AdminGate } from "../gate";

const SUBJECTS = ["", "MAE101", "MAD101", "MAI391", "MAS291"];

export default function AttemptsPage() {
  return (
    <main>
      <h1>Bài làm</h1>
      <p className="lead">
        Bài làm gần nhất, đã chấm. Đây cũng là nguồn cho{" "}
        <span className="mono">scripts/label_real_errors.py</span> — công cụ gán nhãn lỗi
        THẬT của sinh viên, thứ mà phần đánh giá của đồ án đang cần.
      </p>
      <AdminGate>{(token) => <Table token={token} />}</AdminGate>
    </main>
  );
}

function Table({ token }: { token: string }) {
  const [rows, setRows] = useState<AttemptRow[] | null>(null);
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(() => {
    setRows(null);
    setError(null);
    api
      .adminAttempts(token, 200, subject || undefined)
      .then(setRows)
      .catch((exc: Error) => setError(exc.message));
  }, [token, subject]);

  useEffect(reload, [reload]);

  async function download() {
    setSaving(true);
    setError(null);
    try {
      const blob = await api.adminExport(token, subject || undefined);
      // Khoá đi qua header nên không nhúng được vào <a href>; phải tải bằng
      // fetch rồi tự tạo link tạm từ blob.
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = subject ? `attempts-${subject}.csv` : "attempts.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="panel">
        <div className="row spread">
          <div style={{ minWidth: 200 }}>
            <label htmlFor="filter-subject">Lọc theo môn</label>
            <select
              id="filter-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              {SUBJECTS.map((code) => (
                <option key={code || "all"} value={code}>
                  {code || "Tất cả các môn"}
                </option>
              ))}
            </select>
          </div>
          <div className="row tight">
            <button type="button" className="secondary" onClick={reload}>
              Tải lại
            </button>
            <button type="button" onClick={download} disabled={saving}>
              {saving && <span className="spin" aria-hidden="true" />}
              Xuất CSV
            </button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      {rows === null ? (
        <div className="panel">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton w60" />
        </div>
      ) : rows.length === 0 ? (
        <div className="panel empty">Chưa có bài làm nào.</div>
      ) : (
        <div className="panel flush">
          <div className="panel-body scroll-x">
            <table>
              <caption className="sr-only">Bài làm gần nhất của người học</caption>
              <thead>
                <tr>
                  <th scope="col">Thời điểm</th>
                  <th scope="col">Người học</th>
                  <th scope="col">Mã đề</th>
                  <th scope="col">Bài làm</th>
                  <th scope="col">Kết quả chấm</th>
                  <th scope="col">Mã lỗi</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.attempt_id}>
                    <td className="meta" style={{ whiteSpace: "nowrap" }}>{when(row.created_at)}</td>
                    <td>{row.user_id}</td>
                    <td className="mono" style={{ whiteSpace: "nowrap" }}>{row.item_id}</td>
                    <td className="mono">{row.answer || <span className="meta">(trống)</span>}</td>
                    <td>
                      <span className={`chip ${verdictClass(row.verdict)}`}>{row.verdict}</span>
                    </td>
                    <td className="mono meta">{row.error_codes.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="meta">
        Hiện tối đa 200 dòng gần nhất. Bản xuất CSV lấy tới 500 dòng và có BOM nên Excel
        trên Windows đọc đúng tiếng Việt.
      </p>
    </>
  );
}

function verdictClass(verdict: string): string {
  if (verdict === "đúng") return "ok";
  if (verdict === "sai") return "wrong";
  return "warn";
}
