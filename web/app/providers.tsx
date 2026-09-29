"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
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

type Ctx = {
  ready: boolean;
  theme: Theme;
  setTheme: (theme: Theme) => void;
  role: Role;
  setRole: (role: Role) => void;
  scope: Scope;
  setScope: (scope: Scope) => void;
};

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
    () => ({ ready, theme, setTheme, role, setRole, scope, setScope }),
    [ready, theme, setTheme, role, setRole, scope, setScope]
  );

  return (
    <AppContext.Provider value={value}>
      <div className="shell">
        <main>{children}</main>
        <aside className="side">
          <Sidebar />
        </aside>
      </div>
    </AppContext.Provider>
  );
}
