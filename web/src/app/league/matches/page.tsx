"use client";

import { useState } from "react";
import { LeagueShell } from "@/components/LeagueShell";
import { Matchup } from "@/components/Matchup";
import { ScoreForm } from "@/components/ScoreForm";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { Term, a, term } from "@/lib/terms";
import { useLoader } from "@/lib/useLoader";
import type { League, Match, TeamRef } from "@/lib/types";

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

  const { data: teams } = useLoader(() => api.listTeams(league.id), [league.id]);

  const rounds = new Map<number, Match[]>();
  for (const m of matches ?? []) {
    rounds.set(m.round, [...(rounds.get(m.round) ?? []), m]);
  }

  function onSaved() {
    reload();
    onResult();
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
            {Term("week")} {w}
          </button>
        ))}
      </nav>
      <ErrorBanner message={error} />
      {!matches ? (
        !error && <Loading />
      ) : (
        [...rounds.entries()].map(([round, roundMatches]) => (
          <RoundCard
            key={round}
            round={round}
            matches={roundMatches}
            teams={teams}
            pointsToWin={league.points_to_win}
            onSaved={onSaved}
          />
        ))
      )}
    </section>
  );
}

function RoundCard({
  round,
  matches,
  teams,
  pointsToWin,
  onSaved,
}: {
  round: number;
  matches: Match[];
  teams: TeamRef[] | null;
  pointsToWin: number;
  onSaved: () => void;
}) {
  // With an odd number of teams, whoever has no match this round has a bye,
  // except in the week's catch-up round (fewer games than a full round),
  // where the teams that had byes play each other.
  const playing = new Set(matches.flatMap((m) => [m.team_a.id, m.team_b.id]));
  const byes = (teams ?? []).filter((t) => !playing.has(t.id));
  const catchUp = teams !== null && teams.length % 2 === 1 && matches.length < Math.floor(teams.length / 2);

  return (
    <div className="card">
      <div className="card-head">
        <h3>
          {Term("round")} {round} {catchUp && <span className="badge">{Term("catchUpRound")}</span>}
        </h3>
        {catchUp ? (
          <p className="byes muted">
            {Term("team", 2)} that had {a("bye")} this {term("week")} play each other
          </p>
        ) : (
          byes.length > 0 && (
            <p className="byes muted">
              {Term("bye")}: <strong>{byes.map((t) => t.display_name).join(", ")}</strong>
            </p>
          )
        )}
      </div>
      <ul className="match-list">
        {matches.map((m) => (
          <li key={m.id}>
            <span className={`badge ${m.verified_at ? "verified" : m.status}`}>
              {m.verified_at ? "✓ verified" : m.status === "in_progress" ? `${Term("court")} ${m.court}` : m.status}
            </span>
            <Matchup match={m} />
            <span className="action">
              {m.verified_at ? (
                <span className="muted" title="Verified results can't be changed">
                  🔒 Locked
                </span>
              ) : (
                <span className="result-actions">
                  <ScoreForm
                    key={`${m.id}-${m.status}-${m.score_a}-${m.score_b}`}
                    match={m}
                    pointsToWin={pointsToWin}
                    onSaved={onSaved}
                  />
                  {m.status === "completed" && <VerifyButton match={m} onVerified={onSaved} />}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function VerifyButton({ match, onVerified }: { match: Match; onVerified: () => void }) {
  const [busy, setBusy] = useState(false);

  async function verify() {
    const score = `${match.team_a.display_name} ${match.score_a} – ${match.score_b} ${match.team_b.display_name}`;
    if (!window.confirm(`Verify this result?\n\n${score}\n\nVerified results are locked and can't be changed.`)) {
      return;
    }
    setBusy(true);
    try {
      await api.verifyMatch(match.id);
      onVerified();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <button type="button" className="secondary small" disabled={busy} onClick={verify}>
      Verify
    </button>
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
              <th>{Term("team")}</th>
              <th>P</th>
              <th>W</th>
              <th>L</th>
              <th>+/-</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.team.id}>
                <td>{r.team.display_name}</td>
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
