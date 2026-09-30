"use client";

import { useState } from "react";
import { LeagueShell } from "@/components/LeagueShell";
import { Matchup } from "@/components/Matchup";
import { ScoreForm } from "@/components/ScoreForm";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import type { League, Match } from "@/lib/types";

export default function MatchesPage() {
  // Bumped whenever a result is saved so the standings reload.
  const [resultsVersion, setResultsVersion] = useState(0);
  return (
    <LeagueShell>
      {(league) => (
        <div className="two-col">
          <WeekSchedule league={league} onResult={() => setResultsVersion((v) => v + 1)} />
          <Standings leagueId={league.id} version={resultsVersion} />
        </div>
      )}
    </LeagueShell>
  );
}

function WeekSchedule({ league, onResult }: { league: League; onResult: () => void }) {
  const [week, setWeek] = useState(league.current_week);
  const { data: matches, error, reload } = useLoader(
    () => api.listMatches(league.id, week),
    [league.id, week],
  );

  const rounds = new Map<number, Match[]>();
  for (const m of matches ?? []) {
    rounds.set(m.round, [...(rounds.get(m.round) ?? []), m]);
  }

  return (
    <section className="stack">
      <nav className="tabs weeks">
        {Array.from({ length: league.num_weeks }, (_, i) => i + 1).map((w) => (
          <button
            key={w}
            className={w === week ? "active" : ""}
            onClick={() => setWeek(w)}
          >
            Week {w}
          </button>
        ))}
      </nav>
      <ErrorBanner message={error} />
      {!matches ? (
        !error && <Loading />
      ) : (
        [...rounds.entries()].map(([round, roundMatches]) => (
          <div key={round} className="card">
            <h3>Round {round}</h3>
            <ul className="match-list">
              {roundMatches.map((m) => (
                <li key={m.id}>
                  <span className={`badge ${m.status}`}>
                    {m.status === "in_progress" ? `Court ${m.court}` : m.status}
                  </span>
                  <Matchup match={m} />
                  <span className="action">
                    <ScoreForm
                      key={`${m.id}-${m.status}`}
                      match={m}
                      onSaved={() => {
                        reload();
                        onResult();
                      }}
                    />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}

function Standings({ leagueId, version }: { leagueId: number; version: number }) {
  const { data: rows, error } = useLoader(() => api.standings(leagueId), [leagueId, version]);
  return (
    <section className="card">
      <h2>Standings</h2>
      <ErrorBanner message={error} />
      {rows && (
        <table className="compact">
          <thead>
            <tr>
              <th>Team</th>
              <th>P</th>
              <th>W</th>
              <th>L</th>
              <th>+/-</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.team.id}>
                <td>{r.team.name}</td>
                <td>{r.played}</td>
                <td>{r.wins}</td>
                <td>{r.losses}</td>
                <td>{r.point_diff > 0 ? `+${r.point_diff}` : r.point_diff}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
