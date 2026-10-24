"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Term, a, term } from "@/lib/terms";
import { useLoader } from "@/lib/useLoader";
import type { Match } from "@/lib/types";
import { Matchup } from "./Matchup";
import { ScoreForm } from "./ScoreForm";
import { DuprLegend } from "./TeamName";
import { ErrorBanner, Loading } from "./Status";

const REFRESH_MS = 15_000;

/**
 * Live view for one league:
 *  - "On court": matches in progress, with score entry to finish them.
 *  - "Ready to play": this week's unplayed matches where neither team is on court.
 *  - "Waiting": this week's unplayed matches blocked by a team that's on court.
 */
export function LeagueDashboard({ leagueId }: { leagueId: number }) {
  const [week, setWeek] = useState<number | undefined>(undefined);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, loading, reload } = useLoader(
    () => api.dashboard(leagueId, week),
    [leagueId, week],
  );

  // Other devices may start/finish matches; keep the board fresh.
  useEffect(() => {
    const timer = setInterval(reload, REFRESH_MS);
    return () => clearInterval(timer);
  }, [reload]);

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
    reload();
  }

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBanner message={error} />;

  const { league, free_courts, in_progress, available, waiting } = data;
  // Suggest the earliest round that still has a playable match.
  const earliestRound = available.length ? Math.min(...available.map((m) => m.round)) : undefined;
  const showLegend = [...in_progress, ...available, ...waiting].some(
    (m) => m.team_a.dupr_ready || m.team_b.dupr_ready,
  );
  const isCurrent = data.week === league.current_week;

  return (
    <div className="stack">
      <div className="toolbar">
        <div className="week-picker">
          <button
            className="secondary small"
            disabled={data.week <= 1}
            onClick={() => setWeek(data.week - 1)}
          >
            ‹
          </button>
          <strong>
            {Term("week")} {data.week} of {league.num_weeks}
          </strong>
          <button
            className="secondary small"
            disabled={data.week >= league.num_weeks}
            onClick={() => setWeek(data.week + 1)}
          >
            ›
          </button>
          {isCurrent ? (
            <span className="badge">current {term("week")}</span>
          ) : (
            <button
              className="secondary small"
              onClick={() => act(() => api.setCurrentWeek(league.id, data.week))}
            >
              Make current {term("week")}
            </button>
          )}
        </div>
        <span className="muted">
          {data.completed_count}/{data.total_count} {term("match", data.total_count)} played ·{" "}
          {free_courts.length
            ? `Free ${term("court", free_courts.length)}: ${free_courts.join(", ")}`
            : `All ${term("court", 2)} in use`}
          {showLegend && (
            <>
              {" · "}
              <DuprLegend />
            </>
          )}
        </span>
      </div>

      <ErrorBanner message={actionError ?? error} />

      <section>
        <h2>
          On {term("court")} ({in_progress.length})
        </h2>
        {in_progress.length === 0 ? (
          <p className="muted">No {term("match", 2)} in progress.</p>
        ) : (
          <div className="grid">
            {in_progress.map((m) => (
              <div key={m.id} className="card live">
                <div className="card-head">
                  <span className="badge live">
                    {Term("court")} {m.court}
                  </span>
                  <span className="muted">
                    {Term("week")} {m.week} · {Term("round")} {m.round}
                  </span>
                </div>
                <ScoreForm
                  match={m}
                  pointsToWin={league.points_to_win}
                  onSaved={reload}
                  layout="board"
                  showDupr
                />
                <button className="link" onClick={() => act(() => api.cancelMatch(m.id))}>
                  Return to schedule
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2>Ready to play ({available.length})</h2>
        {available.length === 0 ? (
          <p className="muted">No {term("match", 2)} available right now.</p>
        ) : (
          <MatchList
            matches={available}
            highlightRound={earliestRound}
            action={(m) => (
              <StartButton
                match={m}
                freeCourts={free_courts}
                onStart={(court) => act(() => api.startMatch(m.id, court))}
              />
            )}
          />
        )}
      </section>

      {waiting.length > 0 && (
        <section>
          <h2>
            Waiting on {a("team")} ({waiting.length})
          </h2>
          <MatchList
            matches={waiting}
            muted
            action={() => (
              <span className="muted">
                {term("team")} on {term("court")}
              </span>
            )}
          />
        </section>
      )}
    </div>
  );
}

function MatchList({
  matches,
  action,
  muted,
  highlightRound,
}: {
  matches: Match[];
  action: (m: Match) => React.ReactNode;
  muted?: boolean;
  /** Matches from this round are marked as the suggested next games. */
  highlightRound?: number;
}) {
  return (
    <ul className={`match-list ${muted ? "muted" : ""}`}>
      {matches.map((m) => {
        const suggested = m.round === highlightRound;
        return (
          <li key={m.id} className={suggested ? "suggested" : undefined}>
            <span className="round" title={`${Term("round")} ${m.round}`}>
              {Term("round").charAt(0)}
              {m.round}
            </span>
            <Matchup match={m} showDupr />
            {suggested && <span className="badge suggested">Earliest {term("round")}</span>}
            <span className="action">{action(m)}</span>
          </li>
        );
      })}
    </ul>
  );
}

function StartButton({
  match,
  freeCourts,
  onStart,
}: {
  match: Match;
  freeCourts: number[];
  onStart: (court: number) => void;
}) {
  const [court, setCourt] = useState<number | "">("");
  const selected = court === "" ? freeCourts[0] : court;

  if (freeCourts.length === 0) {
    return <span className="muted">no free {term("court")}</span>;
  }
  return (
    <span className="start">
      <select
        aria-label={`${Term("court")} for ${term("match")} ${match.id}`}
        value={selected}
        onChange={(e) => setCourt(Number(e.target.value))}
      >
        {freeCourts.map((c) => (
          <option key={c} value={c}>
            {Term("court")} {c}
          </option>
        ))}
      </select>
      <button className="small" onClick={() => onStart(selected)}>
        Start
      </button>
    </span>
  );
}
