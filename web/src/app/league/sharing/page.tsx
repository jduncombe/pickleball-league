"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LeagueShell } from "@/components/LeagueShell";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { term } from "@/lib/terms";
import type { League } from "@/lib/types";
import { useLoader } from "@/lib/useLoader";

export default function SharingPage() {
  return <LeagueShell allowSetup>{(league) => <Sharing league={league} />}</LeagueShell>;
}

/** Who runs this league: its owner, and the users they've shared it with. */
function Sharing({ league }: { league: League }) {
  const { user } = useAuth();
  const router = useRouter();
  const { data: sharing, error, reload } = useLoader(() => api.sharing(league.id), [league.id]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  if (error) return <ErrorBanner message={error} />;
  if (!sharing || !user) return <Loading />;
  const canChange = user.role === "admin" || sharing.owner?.id === user.id;

  /** Run a change and reload; false (with the error shown) if it failed. */
  async function act(action: () => Promise<unknown>): Promise<boolean> {
    setActionError(null);
    try {
      await action();
      await reload();
      return true;
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
      return false;
    }
  }

  return (
    <div className="stack sharing">
      <p className="muted">
        People this {term("league")} is shared with can do everything its owner can (setup, schedule, results,
        the scoring app) except delete the {term("league")} or change who it&apos;s shared with.
      </p>
      <ErrorBanner message={actionError} />

      <table>
        <tbody>
          <tr>
            <td>
              <strong>{sharing.owner?.name ?? "No owner"}</strong>
              {sharing.owner && <div className="muted small">{sharing.owner.email}</div>}
            </td>
            <td>
              <span className="badge">owner</span>
            </td>
            <td />
          </tr>
          {sharing.members.map((m) => {
            const isMe = m.user.id === user.id;
            return (
              <tr key={m.user.id}>
                <td>
                  <strong>{m.user.name}</strong>
                  {isMe && " (you)"}
                  <div className="muted small">{m.user.email}</div>
                </td>
                <td className="muted small">
                  shared {m.added_by ? `by ${m.added_by.name} ` : ""}
                  {new Date(m.added_at).toLocaleDateString()}
                </td>
                <td className="row-actions">
                  {(canChange || isMe) && (
                    <button
                      type="button"
                      className="link danger"
                      onClick={() =>
                        isMe
                          ? confirm(`Leave ${league.name}? You'll no longer see it.`) &&
                            api.unshare(league.id, m.user.id).then(
                              () => router.push("/leagues"),
                              (err) => setActionError(err instanceof Error ? err.message : String(err)),
                            )
                          : act(() => api.unshare(league.id, m.user.id))
                      }
                    >
                      {isMe ? "Leave" : "Remove"}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {sharing.members.length === 0 && <p className="muted">Not shared with anyone yet.</p>}

      {canChange && (
        <form
          className="card stack"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            setAdding(true);
            const shared = await act(() => api.share(league.id, String(new FormData(form).get("email"))));
            setAdding(false);
            if (shared) form.reset();
          }}
        >
          <h2>Share with someone</h2>
          <div className="inline-form">
            <input
              name="email"
              type="email"
              required
              placeholder="Their account's email"
              aria-label="Email"
              autoComplete="off"
            />
            <button type="submit" disabled={adding}>
              {adding ? "Sharing…" : "Share"}
            </button>
          </div>
          <p className="muted small">They need a user account; an admin can add one on the Users page.</p>
        </form>
      )}
    </div>
  );
}
