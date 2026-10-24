"use client";

import { LeagueShell } from "@/components/LeagueShell";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import type { League } from "@/lib/types";

export default function TeamsPage() {
  return <LeagueShell>{(league) => <TeamList league={league} />}</LeagueShell>;
}

/** Read-only: teams and players are fixed once the league is created. */
function TeamList({ league }: { league: League }) {
  const { data: teams, error } = useLoader(() => api.listTeams(league.id), [league.id]);

  if (error) return <ErrorBanner message={error} />;
  if (!teams) return <Loading />;
  return (
    <div className="stack">
      <p className="muted">
        Teams and players are fixed for the league. To change them, use <em>Edit setup</em>.
      </p>
      <div className="grid wide">
        {teams.map((team) => (
          <div key={team.id} className="card">
            <div className="card-head">
              <h3>{team.display_name}</h3>
              <span className="muted">Team {team.position}</span>
            </div>
            <table className="compact">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>DUPR ID</th>
                  <th>Rating</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody>
                {team.players.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>
                      <code>{p.dupr_id ?? "—"}</code>
                    </td>
                    {/* Populated by the future DUPR integration. */}
                    <td>{p.dupr_rating?.toFixed(3) ?? "—"}</td>
                    <td>{p.email ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
