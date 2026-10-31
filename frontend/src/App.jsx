import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell.jsx";
import { RequireAuth } from "./components/RouteGuards.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import { useAuth } from "./context/AuthContext.jsx";

const ChatPage = lazy(() => import("./pages/ChatPage.jsx"));
const EligibilityPage = lazy(() => import("./pages/EligibilityPage.jsx"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage.jsx"));
const AboutPage = lazy(() => import("./pages/AboutPage.jsx"));
const AdminPage = lazy(() => import("./pages/AdminPage.jsx"));
const SchemesPage = lazy(() => import("./pages/SchemesPage.jsx"));

function PageLoading() {
  return <div className="page-loading" role="status">Loading workspace…</div>;
}

export default function App() {
  return (
    <RouteTree />
  );
}

function RouteTree() {
  const { error } = useAuth();
  return (
    <>
    {error && <div className="app-notice" role="alert">Could not confirm your saved sign-in session. Some account features may be unavailable until the backend reconnects.</div>}
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/schemes" element={<Suspense fallback={<PageLoading />}><SchemesPage /></Suspense>} />
      <Route element={<RequireAuth />}>
        <Route path="/eligibility" element={<Suspense fallback={<PageLoading />}><EligibilityPage /></Suspense>} />
        <Route element={<AppShell />}>
          <Route path="/chat" element={<Suspense fallback={<PageLoading />}><ChatPage /></Suspense>} />
        </Route>
      </Route>
      <Route element={<AppShell />}>
        <Route path="documents" element={<Suspense fallback={<PageLoading />}><DocumentsPage /></Suspense>} />
        <Route path="about" element={<Suspense fallback={<PageLoading />}><AboutPage /></Suspense>} />
      </Route>
      <Route element={<RequireAuth admin />}>
        <Route path="/admin" element={<Suspense fallback={<PageLoading />}><AdminPage /></Suspense>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  );
}
