"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { AUTH_EVENT, api, type User } from "../lib/api";
import { clearSession } from "../lib/session";
import {
  EMPTY_SCOPE,
  loadRole,
  loadScope,
  loadTheme,
  saveRole,
  saveScope,
  saveTheme,
  type Role,
  type Scope,
  type Theme,
} from "../lib/prefs";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

type Ctx = {
  ready: boolean;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  role: Role;
  setRole: (role: Role) => void;
  scope: Scope;
  setScope: (scope: Scope) => void;
  /** `undefined` = đang hỏi server; `null` = chưa đăng nhập. */
  user: User | null | undefined;
  setUser: (user: User | null) => void;
  logout: () => Promise<void>;
};

/** Trang cần tài khoản: chưa đăng nhập thì chuyển sang /login rồi quay lại. */
const PROTECTED = ["/practice", "/ask", "/progress", "/account"];

const AppContext = createContext<Ctx | null>(null);

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp phải nằm trong <Providers>");
  return ctx;
}

export function Providers({ children }: { children: React.ReactNode }) {
  // `ready` phân biệt "chưa đọc localStorage" với "đọc rồi, đúng là rỗng".
  // Thiếu cờ này thì lần vẽ đầu luôn dùng giá trị mặc định và giao diện nhảy
  // một nhịp khi tuỳ chọn thật được nạp.
  const [ready, setReady] = useState(false);
  const [theme, setThemeState] = useState<Theme>("system");
  const [role, setRoleState] = useState<Role>("student");
  const [scope, setScopeState] = useState<Scope>(EMPTY_SCOPE);
  const [user, setUserState] = useState<User | null | undefined>(undefined);
  const path = usePathname();
  const router = useRouter();

  useEffect(() => {
    api.me().then(setUserState).catch(() => setUserState(null));
    // Phiên hết hạn giữa chừng (API trả 401): coi như đã đăng xuất.
    const expired = () => setUserState(null);
    window.addEventListener(AUTH_EVENT, expired);
    return () => window.removeEventListener(AUTH_EVENT, expired);
  }, []);

  useEffect(() => {
    if (user === null && PROTECTED.some((p) => path.startsWith(p))) {
      router.replace(`/login?next=${encodeURIComponent(path)}`);
    }
  }, [user, path, router]);

  // Phiên luyện tập còn sót của tài khoản khác thì các trang tự bỏ qua (so userId),
  // nên đăng nhập không cần xoá gì — đăng nhập lại vẫn học tiếp đúng chỗ.
  const setUser = useCallback((next: User | null) => setUserState(next), []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    clearSession();
    // Tải lại hẳn trang chủ: xoá sạch trạng thái của người vừa đăng xuất trong bộ
    // nhớ, và không vướng bộ chặn "trang cần đăng nhập" đang ở trang hiện tại.
    window.location.assign("/");
  }, []);

  useEffect(() => {
    setThemeState(loadTheme());
    setRoleState(loadRole());
    setScopeState(loadScope());
    setReady(true);
  }, []);

  // Chủ đề đặt trên <html> chứ không trên <body>: nền của trang do
  // `html` quyết định khi cuộn quá mép, để trên body thì lúc cuộn đà trên
  // điện thoại sẽ loé ra một dải màu của chủ đề kia.
  useEffect(() => {
    if (!ready) return;
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
  }, [theme, ready]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    saveTheme(next);
  }, []);

  const setRole = useCallback((next: Role) => {
    setRoleState(next);
    saveRole(next);
  }, []);

  const setScope = useCallback((next: Scope) => {
    setScopeState(next);
    saveScope(next);
  }, []);

  const value = useMemo(
    () => ({ ready, theme, setTheme, role, setRole, scope, setScope, user, setUser, logout }),
    [ready, theme, setTheme, role, setRole, scope, setScope, user, setUser, logout]
  );

  return (
    <AppContext.Provider value={value}>
      <Topbar />
      <div className="shell">
        <aside className="side">
          <Sidebar />
        </aside>
        <div className="content">{children}</div>
      </div>
    </AppContext.Provider>
  );
}
