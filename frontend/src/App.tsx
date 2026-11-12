import { useCallback, useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { api, setUnauthorizedHandler } from "./api";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Connect from "./pages/Connect";
import Dineout from "./pages/Dineout";
import Home from "./pages/Home";
import Households from "./pages/Households";
import Instamart from "./pages/Instamart";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "households", element: <Households /> },
      { path: "connect", element: <Connect /> },
      { path: "dineout", element: <Dineout /> },
      { path: "instamart", element: <Instamart /> },
      { path: "chat", element: <Chat /> },
    ],
  },
]);

/** Gates the whole app behind the app-level session login (see
 * app/session_auth.py) -- distinct from Swiggy OAuth, which /connect
 * handles per-household inside the app once past this gate. Any /api/*
 * call that comes back 401 (session expired, logged out elsewhere, etc.)
 * flips this back to the login screen too, via setUnauthorizedHandler. */
function AuthGate() {
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");

  const check = useCallback(() => {
    api
      .me()
      .then(() => setStatus("authenticated"))
      .catch(() => setStatus("unauthenticated"));
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setStatus("unauthenticated"));
    check();
    return () => setUnauthorizedHandler(null);
  }, [check]);

  if (status === "loading") {
    return <div className="min-h-svh" />;
  }
  if (status === "unauthenticated") {
    return <Login onSuccess={() => setStatus("authenticated")} />;
  }
  return <RouterProvider router={router} />;
}

export default function App() {
  return <AuthGate />;
}
