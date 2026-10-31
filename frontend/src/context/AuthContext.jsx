import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  fetchCurrentUser,
  loginAccount,
  logoutAccount,
  registerAccount,
} from "../services/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const initialUserLoad = useRef(null);

  useEffect(() => {
    let active = true;
    initialUserLoad.current ??= fetchCurrentUser();
    initialUserLoad.current
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (credentials) => {
    const result = await loginAccount(credentials);
    setUser(result.user);
    setSigningOut(false);
    setError("");
    return result.user;
  }, []);

  const signUp = useCallback(async (credentials) => {
    const result = await registerAccount(credentials);
    setUser(result.user);
    setSigningOut(false);
    setError("");
    return result.user;
  }, []);

  const signOut = useCallback(async () => {
    await logoutAccount();
    setSigningOut(true);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, signingOut, signIn, signUp, signOut }),
    [user, loading, error, signingOut, signIn, signUp, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
