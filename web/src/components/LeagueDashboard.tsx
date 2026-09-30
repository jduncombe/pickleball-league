"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import type { Match } from "@/lib/types";
import { Matchup } from "./Matchup";
import { ScoreForm } from "./ScoreForm";
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
            Week {data.week} of {league.num_weeks}
          </strong>
          <button
            className="secondary small"
            disabled={data.week >= league.num_weeks}
            onClick={() => setWeek(data.week + 1)}
          >
            ›
          </button>
          {isCurrent ? (
            <span className="badge">current week</span>
          ) : (
            <button
              className="secondary small"
              onClick={() => act(() => api.updateLeague(league.id, { current_week: data.week }))}
            >
              Make current week
            </button>
          )}
        </div>
        <span className="muted">
          {data.completed_count}/{data.total_count} matches played ·{" "}
          {free_courts.length ? `Free courts: ${free_courts.join(", ")}` : "All courts in use"}
        </span>
      </div>

      <ErrorBanner message={actionError ?? error} />

      <section>
        <h2>On court ({in_progress.length})</h2>
        {in_progress.length === 0 ? (
          <p className="muted">No matches in progress.</p>
        ) : (
          <div className="grid">
            {in_progress.map((m) => (
              <div key={m.id} className="card live">
                <div className="card-head">
                  <span className="badge live">Court {m.court}</span>
                  <span className="muted">
                    Week {m.week} · Round {m.round}
                  </span>
                </div>
                <Matchup match={m} />
                <ScoreForm match={m} onSaved={reload} />
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
          <p className="muted">No match-ups available right now.</p>
        ) : (
          <MatchList
            matches={available}
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
          <h2>Waiting on a team ({waiting.length})</h2>
          <MatchList
            matches={waiting}
            muted
            action={() => <span className="muted">team on court</span>}
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
}: {
  matches: Match[];
  action: (m: Match) => React.ReactNode;
  muted?: boolean;
}) {
  return (
    <ul className={`match-list ${muted ? "muted" : ""}`}>
      {matches.map((m) => (
        <li key={m.id}>
          <span className="round">R{m.round}</span>
          <Matchup match={m} />
          <span className="action">{action(m)}</span>
        </li>
      ))}
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
    return <span className="muted">no free court</span>;
  }
  return (
    <span className="start">
      <select
        aria-label={`Court for match ${match.id}`}
        value={selected}
        onChange={(e) => setCourt(Number(e.target.value))}
      >
        {freeCourts.map((c) => (
          <option key={c} value={c}>
            Court {c}
          </option>
        ))}
      </select>
      <button className="small" onClick={() => onStart(selected)}>
        Start
      </button>
    </span>
  );
}
