import type { ReactNode } from "react";

//import LoginPage from "../pages/LoginPage";
//import { useAuth } from "../hooks/useAuth";

export default function AuthGate({ children }: { children: ReactNode }) {
  //  const { isAuthenticated } = useAuth();
  //return isAuthenticated ? <>{children}</> : <LoginPage />;
  return <>{children}</>;
}
