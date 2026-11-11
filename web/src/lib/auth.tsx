"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Loading } from "@/components/Status";
import { api, SIGNED_OUT_EVENT } from "./api";
import type { User } from "./types";

type AuthState = { status: "loading" } | { status: "signed-out" } | { status: "signed-in"; user: User };

type AuthContextValue = {
  /** Null on the sign-in page while signed out. */
  user: User | null;
  /** Re-read the session, e.g. right after signing in. */
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  refresh: async () => {},
  signOut: async () => {},
});

export const useAuth = () => useContext(AuthContext);

const LOGIN_PATH = "/login";

export const isLoginPath = (path: string) => path.replace(/\/$/, "") === LOGIN_PATH;

/** Only same-site paths, so ?next= can't send someone to another site. */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !isLoginPath(next.split("?")[0])
    ? next
    : "/";
}

/**
 * Every page but the sign-in page needs a session: while there isn't one,
 * render nothing but a redirect to /login/?next=<this page>.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const refresh = useCallback(async () => {
    try {
      const user = await api.me();
      setState({ status: "signed-in", user });
    } catch {
      setState({ status: "signed-out" });
    }
  }, []);

  useEffect(() => {
    let current = true;
    api.me().then(
      (user) => current && setState({ status: "signed-in", user }),
      () => current && setState({ status: "signed-out" }),
    );
    return () => {
      current = false;
    };
  }, []);

  // Any API call answered with 401 (expired or revoked session) signs out here too.
  useEffect(() => {
    const onSignedOut = () => setState({ status: "signed-out" });
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
  }, []);

  const onLoginPage = isLoginPath(pathname);
  useEffect(() => {
    if (state.status === "signed-out" && !onLoginPage) {
      const here = window.location.pathname + window.location.search;
      router.replace(`${LOGIN_PATH}/?next=${encodeURIComponent(here)}`);
    }
  }, [state.status, onLoginPage, router]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setState({ status: "signed-out" });
    }
  }, []);

  const user = state.status === "signed-in" ? state.user : null;
  return (
    <AuthContext.Provider value={{ user, refresh, signOut }}>
      {onLoginPage || user ? children : <Loading />}
    </AuthContext.Provider>
  );
}
