/**
 * Lựa chọn của người dùng lưu ở trình duyệt: chủ đề, vai, phạm vi đang luyện.
 *
 * Mọi hàm đọc/ghi đều bọc try/catch: ở chế độ riêng tư hoặc khi trình duyệt
 * chặn site data, `localStorage` NÉM LỖI chứ không trả null. Không bọc thì cả
 * trang trắng vì một tuỳ chọn giao diện — không đáng.
 */

export type Theme = "light" | "dark" | "system";
export type Role = "student" | "admin";

/** Phạm vi luyện tập, thu hẹp dần. Rỗng nghĩa là "cả môn". */
export type Scope = {
  chapter: string | null;
  skill: string | null;
  topic: string | null;
};

export const EMPTY_SCOPE: Scope = { chapter: null, skill: null, topic: null };

const K_THEME = "ai-tutor-theme";
const K_ROLE = "ai-tutor-role";
const K_SCOPE = "ai-tutor-scope";
const K_ADMIN = "ai-tutor-admin-token";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* chế độ riêng tư: bỏ qua, phiên này vẫn dùng được, chỉ không nhớ */
  }
}

export function loadTheme(): Theme {
  const value = read(K_THEME);
  return value === "light" || value === "dark" ? value : "system";
}

export function saveTheme(theme: Theme): void {
  write(K_THEME, theme === "system" ? null : theme);
}

export function loadRole(): Role {
  return read(K_ROLE) === "admin" ? "admin" : "student";
}

export function saveRole(role: Role): void {
  write(K_ROLE, role === "admin" ? "admin" : null);
}

export function loadScope(): Scope {
  try {
    const raw = read(K_SCOPE);
    if (!raw) return EMPTY_SCOPE;
    const parsed = JSON.parse(raw) as Partial<Scope>;
    return {
      chapter: parsed.chapter ?? null,
      skill: parsed.skill ?? null,
      topic: parsed.topic ?? null,
    };
  } catch {
    return EMPTY_SCOPE;
  }
}

export function saveScope(scope: Scope): void {
  const empty = !scope.chapter && !scope.skill && !scope.topic;
  write(K_SCOPE, empty ? null : JSON.stringify(scope));
}

/**
 * Khoá quản trị.
 *
 * Để ở `sessionStorage` chứ không `localStorage`: đóng tab là mất. Đây là khoá
 * mở được dữ liệu bài làm của người thật, giữ nó lâu trên máy dùng chung thì
 * không ổn. Chỗ chặn thật vẫn là server — phía này chỉ là chỗ cầm tạm để khỏi
 * phải gõ lại mỗi lần đổi trang.
 */
export function loadAdminToken(): string {
  try {
    return sessionStorage.getItem(K_ADMIN) ?? "";
  } catch {
    return "";
  }
}

export function saveAdminToken(token: string): void {
  try {
    if (token) sessionStorage.setItem(K_ADMIN, token);
    else sessionStorage.removeItem(K_ADMIN);
  } catch {
    /* bỏ qua */
  }
}
