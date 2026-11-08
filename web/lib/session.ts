/**
 * Phiên LUYỆN TẬP (môn đang học, mã phiên) lưu ở localStorage để mở lại trang là
 * học tiếp. Danh tính KHÔNG nằm ở đây: nó là cookie đăng nhập httpOnly. `userId`
 * chỉ để nhận ra phiên của tài khoản khác còn sót trên cùng máy và bỏ qua nó.
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
