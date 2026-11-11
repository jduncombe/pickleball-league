"use client";

import { useState } from "react";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { term } from "@/lib/terms";
import type { Role, User } from "@/lib/types";
import { useLoader } from "@/lib/useLoader";

const ROLES: { value: Role; label: string; help: string }[] = [
  {
    value: "admin",
    label: "Admin",
    help: `Everything, including every ${term("league")} and these accounts.`,
  },
  { value: "user", label: "User", help: `Creates and runs their own ${term("league", 2)}.` },
  { value: "umpire", label: "Umpire", help: "Scoring app only: claims courts and records scores." },
];

const MIN_PASSWORD = 12;

/** Account management, for admins. */
export default function UsersPage() {
  const { user: me } = useAuth();
  const { data: users, error, reload } = useLoader(() => api.listUsers());
  const [actionError, setActionError] = useState<string | null>(null);

  if (me?.role !== "admin") return <p className="muted">Only admins can manage accounts.</p>;
  if (error) return <ErrorBanner message={error} />;
  if (!users) return <Loading />;

  async function act(action: () => Promise<unknown>) {
    setActionError(null);
    try {
      await action();
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="stack">
      <h1>Users</h1>
      <p className="muted">
        People sign in with their email, password and an authenticator app. They set the app up at their first
        sign-in. Umpires sign in on the scoring app, not here.
      </p>
      <NewUserForm onCreated={reload} />
      <ErrorBanner message={actionError} />
      <div className="table-scroll">
        <table className="users">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Status</th>
              <th>Last sign-in</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <UserRow key={u.id} user={u} isMe={u.id === me.id} act={act} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UserRow({
  user,
  isMe,
  act,
}: {
  user: User;
  isMe: boolean;
  act: (action: () => Promise<unknown>) => Promise<void>;
}) {
  const [settingPassword, setSettingPassword] = useState(false);
  return (
    <tr className={user.is_active ? undefined : "inactive"}>
      <td>
        <strong>{user.name}</strong>
        <div className="muted small">{user.email}</div>
      </td>
      <td>
        <select
          aria-label={`Role for ${user.name}`}
          value={user.role}
          disabled={isMe}
          title={isMe ? "You can't change your own role" : undefined}
          onChange={(e) => act(() => api.updateUser(user.id, { role: e.target.value as Role }))}
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </td>
      <td>
        {!user.is_active ? (
          <span className="badge">deactivated</span>
        ) : user.mfa_enabled ? (
          <span className="badge completed">active</span>
        ) : (
          <span className="badge" title="They set up an authenticator at their next sign-in">
            awaiting first sign-in
          </span>
        )}
      </td>
      <td className="muted small">
        {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "never"}
      </td>
      <td>
        <div className="user-actions">
          {settingPassword ? (
            <form
              className="inline-form"
              onSubmit={(e) => {
                e.preventDefault();
                const password = String(new FormData(e.currentTarget).get("password"));
                act(() => api.updateUser(user.id, { password })).then(() => setSettingPassword(false));
              }}
            >
              <input
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={MIN_PASSWORD}
                placeholder={`New password (${MIN_PASSWORD}+ characters)`}
                aria-label={`New password for ${user.name}`}
                required
                autoFocus
              />
              <button type="submit" className="small">
                Set
              </button>
              <button type="button" className="link" onClick={() => setSettingPassword(false)}>
                Cancel
              </button>
            </form>
          ) : (
            <>
              <button type="button" className="link" onClick={() => setSettingPassword(true)}>
                Set password
              </button>
              {user.mfa_enabled && (
                <button
                  type="button"
                  className="link"
                  onClick={() =>
                    confirm(
                      `Reset ${user.name}'s authenticator? They'll set up a new one at their next sign-in, ` +
                        "and are signed out now.",
                    ) && act(() => api.resetMfa(user.id))
                  }
                >
                  Reset authenticator
                </button>
              )}
              {!isMe && (
                <button
                  type="button"
                  className={user.is_active ? "link danger" : "link"}
                  onClick={() =>
                    (!user.is_active || confirm(`Deactivate ${user.name}? They're signed out now.`)) &&
                    act(() => api.updateUser(user.id, { is_active: !user.is_active }))
                  }
                >
                  {user.is_active ? "Deactivate" : "Reactivate"}
                </button>
              )}
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

function NewUserForm({ onCreated }: { onCreated: () => Promise<void> }) {
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [role, setRole] = useState<Role>("user");

  return (
    <form
      className="card stack"
      onSubmit={async (e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const data = new FormData(form);
        setSaving(true);
        setError(null);
        try {
          await api.createUser({
            email: String(data.get("email")),
            name: String(data.get("name")),
            role,
            password: String(data.get("password")),
          });
          form.reset();
          await onCreated();
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          setSaving(false);
        }
      }}
    >
      <h2>Add a user</h2>
      <ErrorBanner message={error} />
      <div className="field-grid">
        <label className="field">
          <span>Name</span>
          <input name="name" required maxLength={120} />
        </label>
        <label className="field">
          <span>Email</span>
          <input name="email" type="email" required maxLength={254} autoComplete="off" />
        </label>
        <label className="field">
          <span>Temporary password</span>
          <input
            name="password"
            type="password"
            required
            minLength={MIN_PASSWORD}
            maxLength={256}
            autoComplete="new-password"
          />
        </label>
        <label className="field">
          <span>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">{ROLES.find((r) => r.value === role)?.help}</p>
      <div>
        <button type="submit" disabled={saving}>
          {saving ? "Adding…" : "Add user"}
        </button>
      </div>
    </form>
  );
}
