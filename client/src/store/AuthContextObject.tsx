import { createContext } from "react";
import type { AuthState } from "../types/Auth";

export type AuthContextValue = {
  state: AuthState;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);
