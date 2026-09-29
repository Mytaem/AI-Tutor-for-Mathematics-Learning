/**
 * Lớp gọi API. Toàn bộ nghiệp vụ nằm ở FastAPI, đây chỉ là client mỏng.
 *
 * Cố ý KHÔNG có bất kỳ logic sư phạm nào ở frontend: không tự chấm, không tự
 * quyết mức gợi ý, không giữ đáp án. Web và bot Telegram phải cho ra cùng một
 * kết quả trên cùng một bài làm, nên chỗ duy nhất được quyết định là backend.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type PublicItem = {
  item_id: string;
  subject: string;
  skills: string[];
  statement_vi: string;
  statement_latex: string;
  answer_type: string;
  variable: string;
  bounds: [string, string] | null;
  difficulty: number;
};

export type Hint = {
  level: number;
  level_label: string;
  text: string;
  source: string;
  error_code: string | null;
  step: number | null;
};

export type StepResult = { step: number; ok: boolean | null; reason: string };

export type AttemptResponse = {
  is_correct: boolean;
  final_answer_correct: boolean | null;
  first_wrong_step: number | null;
  step_results: StepResult[];
  error_codes: string[];
  message: string;
  hint: Hint | null;
  mastery_changes: Record<string, number>;
  placement_mode: boolean;
  placement_remaining: number;
};

export type SkillProgress = {
  skill_id: string;
  name_vi: string;
  mastery: number;
};

export type AskResponse = {
  answer: string;
  sources: string[];
  in_scope: boolean;
  used_llm: boolean;
};

export type Progress = {
  user_id: string;
  skills: SkillProgress[];
  attempts: number;
  correct: number;
};

export type Topic = { topic_id: string; name_vi: string; items: number };

export type Lesson = {
  skill_id: string;
  name_vi: string;
  items: number;
  mastery: number | null;
  topics: Topic[];
};

export type Chapter = {
  chapter: string;
  name_vi: string;
  items: number;
  skills: number;
  mastery: number | null;
  lessons: Lesson[];
};

export type Syllabus = { subject: string; items: number; chapters: Chapter[] };

export type SubjectStats = {
  subject: string;
  attempts: number;
  learners: number;
  correct: number;
  unreadable: number;
  accuracy: number | null;
};

export type LearnerRow = {
  user_id: string;
  attempts: number;
  correct: number;
  subjects: number;
  last_seen: number | null;
};

export type AdminOverview = {
  totals: Record<string, number>;
  subjects: SubjectStats[];
  top_error_codes: { error_code: string; count: number }[];
  hint_levels: { level: number; count: number }[];
  learners: LearnerRow[];
  bank: Record<string, number>;
};

export type AttemptRow = {
  attempt_id: number;
  user_id: string;
  subject: string | null;
  item_id: string;
  answer: string;
  verdict: string;
  error_codes: string[];
  created_at: number | null;
};

export type Session = {
  session_id: string;
  user_id: string;
  subject: string;
  first_item: PublicItem | null;
  placement_mode: boolean;
  placement_remaining: number;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    // Thông điệp lỗi của FastAPI nằm ở trường `detail`; hiện nguyên văn cho
    // người dùng thấy còn hơn nuốt lỗi rồi để màn hình trắng.
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Lỗi ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => call<{ status: string; subjects: Record<string, unknown> }>("/health"),
  subjects: () => call<string[]>("/subjects"),

  startSession: (userId: string, subject: string) =>
    call<Session>("/session/start", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, subject }),
    }),

  syllabus: (subject: string, userId?: string) =>
    call<Syllabus>(
      `/syllabus?subject=${encodeURIComponent(subject)}` +
        (userId ? `&user_id=${encodeURIComponent(userId)}` : "")
    ),

  /** `scope` để trống ở tầng nào thì tầng đó không lọc — xem src/core/syllabus.py. */
  nextItem: (
    userId: string,
    subject: string,
    scope?: { chapter?: string | null; skill?: string | null; topic?: string | null }
  ) => {
    const query = new URLSearchParams({ user_id: userId, subject });
    if (scope?.chapter) query.set("chapter", scope.chapter);
    if (scope?.skill) query.set("skill", scope.skill);
    if (scope?.topic) query.set("topic", scope.topic);
    return call<PublicItem>(`/item/next?${query}`);
  },

  adminEnabled: () => call<{ enabled: boolean }>("/admin/enabled"),

  adminOverview: (token: string) =>
    call<AdminOverview>("/admin/overview", { headers: { "X-Admin-Token": token } }),

  adminAttempts: (token: string, limit = 100, subject?: string) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (subject) query.set("subject", subject);
    return call<AttemptRow[]>(`/admin/attempts?${query}`, {
      headers: { "X-Admin-Token": token },
    });
  },

  /** URL tải CSV — khoá đi qua header nên không nhúng được vào thẻ <a>. */
  adminExport: async (token: string, subject?: string) => {
    const query = new URLSearchParams();
    if (subject) query.set("subject", subject);
    const response = await fetch(`${API_URL}/admin/export.csv?${query}`, {
      headers: { "X-Admin-Token": token },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Lỗi ${response.status}`);
    return response.blob();
  },

  submit: (sessionId: string, itemId: string, finalAnswer: string, steps: string[]) =>
    call<AttemptResponse>("/attempt", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        item_id: itemId,
        final_answer: finalAnswer,
        steps,
      }),
    }),

  hint: (sessionId: string, itemId: string, askedForSolution = false) =>
    call<Hint>("/hint", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        item_id: itemId,
        asked_for_solution: askedForSolution,
      }),
    }),

  ask: (question: string, subject?: string, chapter?: string | null) =>
    call<AskResponse>("/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        subject: subject ?? null,
        chapter: chapter ?? null,
      }),
    }),

  progress: (userId: string, subject: string) =>
    call<Progress>(`/progress?user_id=${encodeURIComponent(userId)}&subject=${subject}`),
};
