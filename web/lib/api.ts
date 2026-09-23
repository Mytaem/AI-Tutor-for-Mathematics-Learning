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

export type Progress = {
  user_id: string;
  skills: SkillProgress[];
  attempts: number;
  correct: number;
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

  nextItem: (userId: string, subject: string) =>
    call<PublicItem>(`/item/next?user_id=${encodeURIComponent(userId)}&subject=${subject}`),

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

  progress: (userId: string, subject: string) =>
    call<Progress>(`/progress?user_id=${encodeURIComponent(userId)}&subject=${subject}`),
};
