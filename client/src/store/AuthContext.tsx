// client/src/store/AuthProvider.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AuthState, JwtPayload } from "../types/Auth";
import { AuthService, decodeJwt } from "../services/auth";
import { setAuthToken, setUnauthorizedHandler } from "../services/api";
import { AuthContext } from "./AuthContextObject";

const STORAGE_KEY = "auth.token";
const STORAGE_TYPE = "auth.token.type";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    tokenType: null,
    payload: null,
  });
  const logoutTimer = useRef<number | null>(null);
  const service = useMemo(() => new AuthService(), []);

  const applyToken = useCallback(
    (token: string | null, tokenType: string | null) => {
      setAuthToken(token);
      if (token) {
        sessionStorage.setItem(STORAGE_KEY, token);
        if (tokenType) sessionStorage.setItem(STORAGE_TYPE, tokenType);
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem(STORAGE_TYPE);
      }
    },
    [],
  );

  const doLogout = useCallback(() => {
    applyToken(null, null);
    setState({ token: null, tokenType: null, payload: null });
  }, [applyToken]);

  const scheduleAutoLogout = useCallback(
    (payload: JwtPayload | null) => {
      if (logoutTimer.current) {
        window.clearTimeout(logoutTimer.current);
        logoutTimer.current = null;
      }
      if (!payload?.exp) return;

      const msUntilExpiry = payload.exp * 1000 - Date.now();
      if (msUntilExpiry <= 0) {
        doLogout();
        return;
      }
      const timeoutMs = Math.max(1000, msUntilExpiry - 5000);
      logoutTimer.current = window.setTimeout(
        () => doLogout(),
        timeoutMs,
      ) as unknown as number;
    },
    [doLogout],
  );

  useEffect(() => {
    setUnauthorizedHandler(doLogout);
  }, [doLogout]);

  useEffect(() => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    const savedType = sessionStorage.getItem(STORAGE_TYPE) ?? "bearer";
    if (saved) {
      const payload = decodeJwt(saved);
      setState({ token: saved, tokenType: savedType, payload });
      applyToken(saved, savedType);
      scheduleAutoLogout(payload);
    }
  }, [applyToken, scheduleAutoLogout]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { token, tokenType, payload } = await service.login(
        username,
        password,
      );
      setState({ token, tokenType, payload });
      applyToken(token, tokenType);
      scheduleAutoLogout(payload);
    },
    [applyToken, scheduleAutoLogout, service],
  );

  const value = useMemo(
    () => ({
      state,
      isAuthenticated: !!state.token,
      login,
      logout: doLogout,
    }),
    [state, login, doLogout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
