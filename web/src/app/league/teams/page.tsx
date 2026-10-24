"use client";

import { useState } from "react";
import { LeagueShell } from "@/components/LeagueShell";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import { DUPR_ID_PATTERN, DUPR_ID_TITLE } from "@/lib/teams";
import type { Team } from "@/lib/types";

export default function TeamsPage() {
  return <LeagueShell>{(league) => <TeamList leagueId={league.id} />}</LeagueShell>;
}

function TeamList({ leagueId }: { leagueId: number }) {
  const { data: teams, error, reload } = useLoader(() => api.listTeams(leagueId), [leagueId]);

  if (error) return <ErrorBanner message={error} />;
  if (!teams) return <Loading />;
  return (
    <div className="stack">
      <p className="muted">
        Teams were set up with the league. Names are optional: a team without one is shown by its
        players&apos; names.
      </p>
      <div className="grid wide">
        {teams.map((team) => (
          <TeamCard key={team.id} team={team} onChange={reload} />
        ))}
      </div>
    </div>
  );
}

function TeamCard({ team, onChange }: { team: Team; onChange: () => void }) {
  const [name, setName] = useState(team.name ?? "");
  const nameChanged = name.trim() !== (team.name ?? "");
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>): Promise<boolean> {
    try {
      await fn();
      setError(null);
      onChange();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return false;
    }
  }

  return (
    <div className="card">
      <div className="card-head">
        <h3>{team.display_name}</h3>
        <span className="muted">Team {team.position}</span>
      </div>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => api.renameTeam(team.id, name.trim()));
        }}
      >
        <input
          aria-label={`Team ${team.position} name (optional)`}
          placeholder="Team name (optional)"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {nameChanged && <button className="small">{name.trim() ? "Save name" : "Clear name"}</button>}
      </form>

      <ErrorBanner message={error} />

      {team.players.length > 0 && (
        <table className="compact">
          <thead>
            <tr>
              <th>Player</th>
              <th>Email</th>
              <th>DUPR ID</th>
              <th>Rating</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {team.players.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.email ?? "—"}</td>
                <td>
                  <code>{p.dupr_id ?? "—"}</code>
                </td>
                {/* Populated by the future DUPR integration. */}
                <td>{p.dupr_rating?.toFixed(3) ?? "—"}</td>
                <td>
                  <button
                    className="link danger"
                    onClick={() => run(() => api.deletePlayer(p.id))}
                    aria-label={`Remove ${p.name}`}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <AddPlayerForm onAdd={(input) => run(() => api.addPlayer(team.id, input))} />
    </div>
  );
}

function AddPlayerForm({
  onAdd,
}: {
  onAdd: (input: { name: string; email: string; dupr_id: string }) => Promise<boolean>;
}) {
  const empty = { name: "", email: "", dupr_id: "" };
  const [form, setForm] = useState(empty);

  return (
    <form
      className="add-player"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await onAdd(form)) setForm(empty);
      }}
    >
      <input
        required
        placeholder="Player name"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <input
        type="email"
        placeholder="Email (optional)"
        value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })}
      />
      <input
        placeholder="DUPR ID (optional)"
        pattern={DUPR_ID_PATTERN}
        title={DUPR_ID_TITLE}
        value={form.dupr_id}
        onChange={(e) => setForm({ ...form, dupr_id: e.target.value })}
      />
      <button className="small">Add player</button>
    </form>
  );
}
