import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, session, type User } from "../lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(session.token));

  const logout = useCallback(() => {
    session.set(null);
    setUser(null);
  }, []);

  useEffect(() => {
    session.onUnauthorized(() => setUser(null));
    if (!session.token) return;
    api
      .me()
      .then(setUser)
      .catch(() => session.set(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.login(username, password);
    session.set(result.access_token);
    setUser(result.user);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}

/** Para as telas que só existem com alguém logado. */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("Nenhum usuário logado");
  return user;
}
