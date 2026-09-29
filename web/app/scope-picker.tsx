"use client";

import { useEffect, useState } from "react";
import { api, type Syllabus } from "../lib/api";
import { EMPTY_SCOPE, type Scope } from "../lib/prefs";
import { useApp } from "./providers";

/**
 * Chọn phạm vi luyện tập: chương → bài → dạng bài.
 *
 * Hai quy tắc, và cả hai đều để người học không bấm vào chỗ trống:
 *
 *  - Mỗi lựa chọn hiện SỐ ĐỀ ngay trong nhãn. Nhánh 0 đề bị `disabled`.
 *  - Chọn lại tầng trên thì XOÁ các tầng dưới. Giữ lại thì sinh ra tổ hợp
 *    không tồn tại (chương "Cây" + dạng bài "Euclid") và người học nhận về
 *    lỗi "không có đề" mà không hiểu vì sao.
 */
export function ScopePicker({ subject }: { subject: string | null }) {
  const { scope, setScope } = useApp();
  const [tree, setTree] = useState<Syllabus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!subject) return;
    let alive = true;
    setTree(null);
    setFailed(false);
    api
      .syllabus(subject)
      .then((data) => alive && setTree(data))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [subject]);

  if (!subject) {
    return <p className="meta">Chọn môn trước đã.</p>;
  }
  if (failed) {
    return <p className="meta">Chưa tải được danh sách chương.</p>;
  }
  if (!tree) {
    return (
      <>
        <div className="skeleton tall" />
        <div className="skeleton tall" />
      </>
    );
  }

  const chapter = tree.chapters.find((c) => c.chapter === scope.chapter) ?? null;
  const lesson = chapter?.lessons.find((l) => l.skill_id === scope.skill) ?? null;

  const update = (next: Partial<Scope>) =>
    setScope({ ...scope, ...next } as Scope);

  const narrowed = [scope.chapter, scope.skill, scope.topic].filter(Boolean).length;

  return (
    <div className="stack">
      <div>
        <label htmlFor="pick-chapter">Chương</label>
        <select
          id="pick-chapter"
          value={scope.chapter ?? ""}
          // Đổi chương thì bài và dạng bài phải reset về rỗng.
          onChange={(e) =>
            setScope({ chapter: e.target.value || null, skill: null, topic: null })
          }
        >
          <option value="">Cả môn — {tree.items.toLocaleString("vi-VN")} đề</option>
          {tree.chapters.map((c) => (
            <option key={c.chapter} value={c.chapter} disabled={c.items === 0}>
              {c.name_vi} — {c.items === 0 ? "chưa có đề" : `${c.items} đề`}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="pick-lesson">Bài</label>
        <select
          id="pick-lesson"
          value={scope.skill ?? ""}
          disabled={!chapter}
          onChange={(e) => update({ skill: e.target.value || null, topic: null })}
        >
          <option value="">
            {chapter ? `Cả chương — ${chapter.items} đề` : "Chọn chương trước"}
          </option>
          {(chapter?.lessons ?? []).map((l) => (
            <option key={l.skill_id} value={l.skill_id} disabled={l.items === 0}>
              {l.name_vi} — {l.items === 0 ? "chưa có đề" : `${l.items} đề`}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="pick-topic">Dạng bài</label>
        <select
          id="pick-topic"
          value={scope.topic ?? ""}
          disabled={!lesson}
          onChange={(e) => update({ topic: e.target.value || null })}
        >
          <option value="">
            {lesson ? `Cả bài — ${lesson.items} đề` : "Chọn bài trước"}
          </option>
          {(lesson?.topics ?? []).map((t) => (
            <option key={t.topic_id} value={t.topic_id}>
              {t.name_vi} — {t.items} đề
            </option>
          ))}
        </select>
      </div>

      {chapter?.mastery !== null && chapter?.mastery !== undefined && (
        <p className="meta">
          Mức thành thạo chương này: {(chapter.mastery * 100).toFixed(0)}% — tính theo kỹ
          năng yếu nhất trong chương.
        </p>
      )}

      {narrowed > 0 && (
        <button
          type="button"
          className="secondary small block"
          onClick={() => setScope(EMPTY_SCOPE)}
        >
          Bỏ lọc, luyện cả môn
        </button>
      )}
    </div>
  );
}

/** Một dòng chữ nói phạm vi đang lọc, để hiện trên trang nội dung. */
export function ScopeLine({ subject }: { subject: string | null }) {
  const { scope } = useApp();
  const [tree, setTree] = useState<Syllabus | null>(null);

  useEffect(() => {
    if (!subject) return;
    let alive = true;
    api
      .syllabus(subject)
      .then((data) => alive && setTree(data))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [subject]);

  if (!scope.chapter) return null;

  const chapter = tree?.chapters.find((c) => c.chapter === scope.chapter);
  const lesson = chapter?.lessons.find((l) => l.skill_id === scope.skill);
  const topic = lesson?.topics.find((t) => t.topic_id === scope.topic);

  const parts = [
    chapter?.name_vi ?? scope.chapter,
    lesson?.name_vi ?? scope.skill,
    topic?.name_vi ?? scope.topic,
  ].filter(Boolean);

  return (
    <div className="row tight" style={{ marginBottom: 14 }}>
      {parts.map((part, index) => (
        <span className={index === 0 ? "chip accent" : "chip"} key={`${part}-${index}`}>
          {part}
        </span>
      ))}
    </div>
  );
}
