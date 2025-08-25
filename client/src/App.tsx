import AuthGate from "./auth/AuthGate";
import MainPage from "./pages/MainPage";
import { AuthProvider } from "./store/AuthContext";

export default function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <MainPage />
      </AuthGate>
    </AuthProvider>
  );
}
