/**
 * Phiên làm bài lưu ở localStorage.
 *
 * Chưa có đăng nhập: đồ án cần đo được việc học chứ không cần quản lý tài khoản,
 * và người tham gia thực nghiệm sẽ vào qua một đường link. Danh tính vì thế chỉ
 * là một chuỗi do người dùng tự đặt, đủ để nối các lượt làm bài của cùng một
 * người lại với nhau ở phía server.
 */

const KEY = "ai-tutor-session";

export type StoredSession = {
  sessionId: string;
  userId: string;
  subject: string;
};

export function saveSession(session: StoredSession): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

export function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null; // localStorage bị chặn (chế độ riêng tư) — coi như chưa có phiên
  }
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
}
