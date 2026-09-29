"use client";

import { useEffect, useState } from "react";
import { api, type AdminOverview } from "../../lib/api";
import { rowHeadStyle as headCell, when } from "../../lib/format";
import { AdminGate } from "./gate";

export default function AdminPage() {
  return (
    <main>
      <h1>Tổng quan</h1>
      <p className="lead">
        Dành cho giảng viên: ai đang luyện, sai ở đâu, xin gợi ý tới mức nào. Dữ liệu
        lấy trực tiếp từ bảng <span className="mono">attempts</span> và{" "}
        <span className="mono">hints</span> — chính hai bảng dùng cho phần thực nghiệm
        của đồ án.
      </p>
      <AdminGate>{(token) => <Overview token={token} />}</AdminGate>
    </main>
  );
}

function Overview({ token }: { token: string }) {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .adminOverview(token)
      .then(setData)
      .catch((exc: Error) => setError(exc.message));
  }, [token]);

  if (error) return <p className="error">{error}</p>;
  if (!data) {
    return (
      <div className="tiles">
        <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
        <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
        <div className="tile"><div className="skeleton tall w60" /><div className="skeleton w40" /></div>
      </div>
    );
  }

  const bankTotal = Object.values(data.bank).reduce((sum, n) => sum + n, 0);

  return (
    <>
      <div className="tiles">
        <div className="tile">
          <div className="n">{data.totals.attempts ?? 0}</div>
          <div className="k">Lượt làm bài</div>
        </div>
        <div className="tile">
          <div className="n">{data.learners.length}</div>
          <div className="k">Người học có dữ liệu</div>
        </div>
        <div className="tile">
          <div className="n">{data.totals.hints ?? 0}</div>
          <div className="k">Gợi ý đã cấp</div>
        </div>
        <div className="tile">
          <div className="n">{bankTotal.toLocaleString("vi-VN")}</div>
          <div className="k">Đề trong ngân hàng</div>
        </div>
      </div>

      {(data.totals.attempts ?? 0) === 0 && (
        <div className="banner info">
          <span aria-hidden="true">i</span>
          <div>
            <strong>Chưa có lượt làm bài nào</strong>
            <div className="meta" style={{ marginTop: 4 }}>
              Các bảng dưới sẽ có số ngay khi có người luyện tập qua web hoặc bot.
            </div>
          </div>
        </div>
      )}

      <h2>Theo môn</h2>
      <div className="panel flush">
        <div className="panel-body scroll-x">
          <table>
            <caption className="sr-only">Số lượt, người học và tỉ lệ đúng theo từng môn</caption>
            <thead>
              <tr>
                <th scope="col">Môn</th>
                <th scope="col" className="value">Lượt làm</th>
                <th scope="col" className="value">Người học</th>
                <th scope="col" className="value">Làm đúng</th>
                <th scope="col" className="value">Tỉ lệ đúng</th>
                <th scope="col" className="value">Không đọc được</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((row) => (
                <tr key={row.subject}>
                  <th scope="row" style={headCell}>{row.subject}</th>
                  <td className="value">{row.attempts}</td>
                  <td className="value">{row.learners}</td>
                  <td className="value">{row.correct}</td>
                  <td className="value">
                    {row.accuracy === null ? "—" : `${(row.accuracy * 100).toFixed(0)}%`}
                  </td>
                  <td className="value">{row.unreadable}</td>
                </tr>
              ))}
              {data.subjects.length === 0 && (
                <tr><td colSpan={6} className="meta">Chưa có dữ liệu.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="meta">
        <strong>Tỉ lệ đúng</strong> tính trên số lượt <em>chấm được</em>. Cột{" "}
        <strong>không đọc được</strong> là bài mà bộ chấm từ chối kết luận vì sai định
        dạng — đó là lỗi gõ, không phải lỗi kiến thức, nên không trộn vào tỉ lệ đúng.
        Cột này tăng bất thường nghĩa là ô nhập đáp án đang khó dùng.
      </p>

      <h2>Mã lỗi hay gặp</h2>
      <div className="panel">
        {data.top_error_codes.length === 0 ? (
          <p className="meta">Chưa có mã lỗi nào được ghi.</p>
        ) : (
          <table>
            <caption className="sr-only">Các mã lỗi xuất hiện nhiều nhất</caption>
            <thead>
              <tr>
                <th scope="col">Mã lỗi</th>
                <th scope="col">Số lần</th>
                <th scope="col" className="value">Tỉ lệ</th>
              </tr>
            </thead>
            <tbody>
              {data.top_error_codes.map((row) => {
                const top = data.top_error_codes[0].count || 1;
                return (
                  <tr key={row.error_code}>
                    <th scope="row" className="mono" style={headCell}>{row.error_code}</th>
                    <td>
                      <div className="bar">
                        <span style={{ width: `${Math.max(3, (row.count / top) * 100)}%` }} />
                      </div>
                    </td>
                    <td className="value">{row.count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="meta" style={{ marginTop: 12 }}>
          Đây là chỗ đáng xem nhất để biết nên dạy lại phần nào: một mã lỗi nhảy lên đầu
          nghĩa là cả lớp đang hiểu sai cùng một điều.
        </p>
      </div>

      <h2>Mức gợi ý đã dùng</h2>
      <div className="panel">
        {data.hint_levels.length === 0 ? (
          <p className="meta">Chưa ai xin gợi ý.</p>
        ) : (
          <table>
            <caption className="sr-only">Số gợi ý đã cấp theo từng mức</caption>
            <thead>
              <tr>
                <th scope="col">Mức</th>
                <th scope="col">Số gợi ý</th>
                <th scope="col" className="value">Số lần</th>
              </tr>
            </thead>
            <tbody>
              {data.hint_levels.map((row) => {
                const top = Math.max(...data.hint_levels.map((r) => r.count)) || 1;
                return (
                  <tr key={row.level}>
                    <th scope="row" style={headCell}>Mức {row.level}</th>
                    <td>
                      <div className="bar">
                        <span style={{ width: `${Math.max(3, (row.count / top) * 100)}%` }} />
                      </div>
                    </td>
                    <td className="value">{row.count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="meta" style={{ marginTop: 12 }}>
          Nhiều lượt dồn ở mức 4–5 nghĩa là thang gợi ý chưa đủ sức giúp ở các mức thấp,
          và người học phải leo tới tận lời giải.
        </p>
      </div>

      <h2>Người học</h2>
      <div className="panel flush">
        <div className="panel-body scroll-x">
          <table>
            <caption className="sr-only">Danh sách người học và số lượt làm bài</caption>
            <thead>
              <tr>
                <th scope="col">Người học</th>
                <th scope="col" className="value">Lượt làm</th>
                <th scope="col" className="value">Làm đúng</th>
                <th scope="col" className="value">Số môn</th>
                <th scope="col" className="value">Lần cuối</th>
              </tr>
            </thead>
            <tbody>
              {data.learners.map((row) => (
                <tr key={row.user_id}>
                  <th scope="row" style={headCell}>{row.user_id}</th>
                  <td className="value">{row.attempts}</td>
                  <td className="value">{row.correct}</td>
                  <td className="value">{row.subjects}</td>
                  <td className="value">{when(row.last_seen)}</td>
                </tr>
              ))}
              {data.learners.length === 0 && (
                <tr><td colSpan={5} className="meta">Chưa có ai.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
