"use client";

import { useMemo } from "react";
import katex from "katex";

/**
 * Hiện văn bản có lẫn công thức LaTeX.
 *
 * Backend đã chuẩn hoá mọi kiểu ký hiệu về **một** quy ước (xem
 * `src/rag/mathtext.py`): `$...$` cho công thức trong câu, `$$...$$` cho công
 * thức đứng riêng. Chuẩn hoá ở backend chứ không ở đây là có lý do: bot Telegram
 * cũng cần, và để mỗi kênh tự đoán thì hai kênh sẽ hiển thị khác nhau trên cùng
 * một câu trả lời.
 *
 * Trước khi có component này, trang hỏi lý thuyết in `{answer.answer}` dạng chữ
 * thuần, nên người học thấy nguyên văn `\( \frac{\sigma}{\sqrt{n}} \)`.
 */

type Piece =
  | { kind: "text"; value: string }
  | { kind: "math"; value: string; display: boolean };

/**
 * Tách chuỗi thành các mảnh chữ và mảnh công thức.
 *
 * Quét `$$` TRƯỚC `$`: không thì `$$x$$` bị đọc thành một công thức rỗng `$`,
 * rồi `x`, rồi một công thức rỗng nữa.
 */
export function splitMath(text: string): Piece[] {
  const pieces: Piece[] = [];
  let rest = text;

  while (rest.length > 0) {
    const open = rest.search(/\$\$?/);
    if (open === -1) {
      pieces.push({ kind: "text", value: rest });
      break;
    }

    if (open > 0) pieces.push({ kind: "text", value: rest.slice(0, open) });

    const display = rest.startsWith("$$", open);
    const marker = display ? "$$" : "$";
    const close = rest.indexOf(marker, open + marker.length);

    if (close === -1) {
      // Dấu $ lẻ không có dấu đóng — coi là chữ thường. Model đôi khi viết một
      // dấu $ tiền tệ, và bỏ nguyên văn còn hơn làm mất một đoạn chữ.
      pieces.push({ kind: "text", value: rest.slice(open) });
      break;
    }

    const body = rest.slice(open + marker.length, close).trim();
    if (body) pieces.push({ kind: "math", value: body, display });
    rest = rest.slice(close + marker.length);
  }

  return pieces;
}

export function MathText({ text }: { text: string }) {
  const pieces = useMemo(() => splitMath(text), [text]);

  return (
    <>
      {pieces.map((piece, index) => {
        if (piece.kind === "text") {
          // `pre-wrap` để giữ các dòng trống mà backend chèn quanh công thức
          // đứng riêng.
          return (
            <span key={index} style={{ whiteSpace: "pre-wrap" }}>
              {piece.value}
            </span>
          );
        }

        let html: string;
        try {
          html = katex.renderToString(piece.value, {
            displayMode: piece.display,
            throwOnError: false,
            strict: false,
          });
        } catch {
          // LaTeX hỏng thì hiện nguyên văn trong khối mã, KHÔNG để trống.
          // Người học thấy công thức thô vẫn còn đoán được; thấy khoảng trắng
          // thì không biết là mất chữ hay vốn không có gì.
          return (
            <code key={index} className="mono">
              {piece.value}
            </code>
          );
        }

        return piece.display ? (
          <div key={index} dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <span key={index} dangerouslySetInnerHTML={{ __html: html }} />
        );
      })}
    </>
  );
}
