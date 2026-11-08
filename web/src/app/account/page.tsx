"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorBanner } from "@/components/Status";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ROLE_LABELS = { admin: "Admin", user: "User", umpire: "Umpire" } as const;
const MIN_PASSWORD = 12;

/** Your account: who you're signed in as, and changing your password. */
export default function AccountPage() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  if (!user) return null;

  return (
    <div className="stack account">
      <h1>Your account</h1>
      <p>
        {user.name} · {user.email} · {ROLE_LABELS[user.role]}
      </p>

      <form
        className="card stack"
        onSubmit={async (e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          const next = String(data.get("new_password"));
          if (next !== String(data.get("repeat"))) {
            setError("The new passwords don't match");
            return;
          }
          setSaving(true);
          setError(null);
          try {
            await api.changePassword(String(data.get("current_password")), next, String(data.get("code")));
            await signOut();
            router.replace("/login/");
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          } finally {
            setSaving(false);
          }
        }}
      >
        <h2>Change password</h2>
        <p className="muted small">
          You&apos;ll be signed out everywhere, and sign in again with the new one.
        </p>
        <ErrorBanner message={error} />
        <label className="field">
          <span>Current password</span>
          <input name="current_password" type="password" autoComplete="current-password" required />
        </label>
        <label className="field">
          <span>New password ({MIN_PASSWORD}+ characters)</span>
          <input
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD}
            maxLength={256}
            required
          />
        </label>
        <label className="field">
          <span>New password again</span>
          <input name="repeat" type="password" autoComplete="new-password" required />
        </label>
        <label className="field">
          <span>Code from your authenticator app</span>
          <input name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={7} required />
        </label>
        <div>
          <button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Change password"}
          </button>
        </div>
      </form>
    </div>
  );
}
