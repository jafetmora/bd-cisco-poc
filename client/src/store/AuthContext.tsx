import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AuthState, JwtPayload } from "../types/Auth";
import { decodeJwt } from "../services/auth"; // AuthService
import { setAuthToken, setUnauthorizedHandler } from "../services/api";
import { AuthContext } from "./AuthContextObject";

const USE_FAKE_AUTH = import.meta.env.VITE_AUTH_FAKE === "1";
const STORAGE_KEY = "auth.token";
const STORAGE_TYPE = "auth.token.type";

function b64url(input: string) {
  return btoa(input)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function makeFakeJwt(payload: Record<string, unknown>) {
  const header = { alg: "HS256", typ: "JWT" };
  const p1 = b64url(JSON.stringify(header));
  const p2 = b64url(JSON.stringify(payload));
  const signature = "fake-signature";
  return `${p1}.${p2}.${signature}`;
}

function makeFakePayload(partial?: Partial<JwtPayload>): JwtPayload {
  const nowSec = Math.floor(Date.now() / 1000);
  return {
    sub: partial?.sub ?? "dev-user",
    iat: nowSec,
    exp: partial?.exp ?? nowSec + 60 * 60, // +1h
    ...partial,
  } as JwtPayload;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    tokenType: null,
    payload: null,
  });
  const logoutTimer = useRef<number | null>(null);
  // const service = useMemo(() => new AuthService(), []);

  const applyToken = useCallback(
    (token: string | null, tokenType: string | null) => {
      setAuthToken(token);
      if (token) {
        sessionStorage.setItem(STORAGE_KEY, token);
        sessionStorage.setItem(STORAGE_TYPE, tokenType ?? "bearer");
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
      return;
    }

    if (USE_FAKE_AUTH) {
      const fakePayload = makeFakePayload();
      const fakeToken = makeFakeJwt(fakePayload);
      setState({ token: fakeToken, tokenType: "bearer", payload: fakePayload });
      applyToken(fakeToken, "bearer");
      scheduleAutoLogout(fakePayload);
    }
  }, [applyToken, scheduleAutoLogout]);

  const login = useCallback(
    async (username: string, password: string) => {
      const fakePayload = makeFakePayload({
        sub: `${username} ${password}`,
      });
      const fakeToken = makeFakeJwt(fakePayload);
      setState({ token: fakeToken, tokenType: "bearer", payload: fakePayload });
      applyToken(fakeToken, "bearer");
      scheduleAutoLogout(fakePayload);
      return;

      // const { token, tokenType, payload } = await service.login(username, password);
      // setState({ token, tokenType, payload });
      // applyToken(token, tokenType);
      // scheduleAutoLogout(payload);
    },
    [applyToken, scheduleAutoLogout], // service
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
