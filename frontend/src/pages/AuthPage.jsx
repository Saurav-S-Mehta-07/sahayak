import { useState } from "react";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function AuthPage({ mode }) {
  const isRegister = mode === "register";
  const { user, loading, signIn, signUp } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  if (loading) return <div className="page-loading" role="status">Checking your session…</div>;
  if (user) return <Navigate to={user.role === "admin" ? "/admin" : "/chat"} replace />;

  async function submit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      if (isRegister) await signUp({ email, password });
      else await signIn({ email, password });
      const destination = location.state?.from;
      const target = typeof destination === "string"
        ? destination
        : destination
          ? {
              pathname: destination.pathname,
              search: destination.search,
              hash: destination.hash,
            }
          : "/chat";
      navigate(target, {
        replace: true,
        state: typeof destination === "object" ? destination.state : undefined,
      });
    } catch (cause) {
      setError(cause.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <Link to="/" className="auth-back"><ArrowLeft size={16} /> Back to home</Link>
      <section className="auth-card">
        <Link className="public-brand auth-brand" to="/"><span className="brand-mark"><ShieldCheck size={19} /></span>Yojana Sahayak</Link>
        <span className="eyebrow">{isRegister ? "CREATE YOUR ACCOUNT" : "WELCOME BACK"}</span>
        <h1>{isRegister ? "A clearer next step." : "Continue your conversation."}</h1>
        <p>{isRegister ? "Create a private citizen account to ask questions and keep your conversations." : "Sign in to access your saved conversations."}</p>
        <form className="auth-form" onSubmit={submit}>
          <label>Email address<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label>Password<input type="password" autoComplete={isRegister ? "new-password" : "current-password"} required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} /><small>Use at least 12 characters.</small></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button auth-submit" disabled={pending}>{pending ? "Please wait…" : isRegister ? "Create account" : "Sign in"}</button>
        </form>
        <p className="auth-switch">{isRegister ? "Already have an account?" : "New to Yojana Sahayak?"} <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create an account"}</Link></p>
        <div className="auth-security"><ShieldCheck size={15} /> Your conversations are private to your account.</div>
      </section>
    </main>
  );
}
