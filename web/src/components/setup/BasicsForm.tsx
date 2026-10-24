"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type LeagueBasics, POINTS_OPTIONS, type PointsToWin, type SchedulePreview } from "@/lib/types";
import { ErrorBanner } from "../Status";

type NumberField = "num_teams" | "num_weeks" | "matches_per_week" | "num_courts";

const FIELDS: { key: NumberField; label: string; min: number; max: number; help: string; schedule: boolean }[] = [
  { key: "num_teams", label: "Number of teams", min: 2, max: 64, help: "Players are entered on the next step.", schedule: true },
  { key: "num_weeks", label: "Number of weeks", min: 1, max: 52, help: "Length of the season.", schedule: true },
  // max is also capped at num_teams - 1 (one match against each other team).
  { key: "matches_per_week", label: "Matches per week", min: 1, max: 20, help: "How many matches each team plays each week.", schedule: true },
  { key: "num_courts", label: "Courts in use", min: 1, max: 50, help: "Limits how many matches run at once.", schedule: false },
];

const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

/** The schedule these settings would produce, from the API (debounced). */
function useSchedulePreview(form: LeagueBasics): SchedulePreview | null {
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const { num_teams, num_weeks, matches_per_week } = form;
  useEffect(() => {
    setPreview(null);
    if (!(num_teams >= 2 && num_weeks >= 1 && matches_per_week >= 1 && matches_per_week < num_teams)) return;
    let current = true;
    const timer = setTimeout(() => {
      api
        .schedulePreview({ num_teams, num_weeks, matches_per_week })
        .then((p) => current && setPreview(p))
        .catch(() => {}); // summary just stays without the preview details
    }, 300);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [num_teams, num_weeks, matches_per_week]);
  return preview;
}

export const DEFAULT_BASICS: LeagueBasics = {
  name: "",
  num_teams: 8,
  num_weeks: 8,
  matches_per_week: 3,
  num_courts: 4,
  points_to_win: 11,
  use_team_names: false,
};

/**
 * Setup step 1. `lockedAfterPlay`: matches have been played, so the season's
 * shape and the points to win are fixed.
 */
export function BasicsForm({
  initial,
  lockedAfterPlay = false,
  onSubmit,
}: {
  initial: LeagueBasics;
  lockedAfterPlay?: boolean;
  onSubmit: (basics: LeagueBasics) => Promise<void>;
}) {
  const [form, setForm] = useState<LeagueBasics>(initial);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const preview = useSchedulePreview(form);
  const maxMatches = Math.max(form.num_teams - 1, 1);
  const tooManyMatches = form.matches_per_week > maxMatches;
  const gamesPerRound = Math.floor(form.num_teams / 2);
  const wavesPerRound = Math.ceil(gamesPerRound / Math.max(form.num_courts, 1));
  const n = form.points_to_win;
  const exampleScores = `${n}-${n - 2} or ${n + 1}-${n - 1}`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({ ...form, name: form.name.trim() });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  return (
    <form className="stack narrow" onSubmit={submit}>
      <ErrorBanner message={error} />

      <label className="field">
        <span>League name</span>
        <input
          required
          maxLength={120}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Tuesday Night Doubles"
        />
      </label>

      <div className="field-grid">
        {FIELDS.map((f) => {
          const locked = lockedAfterPlay && f.schedule;
          return (
            <label key={f.key} className="field">
              <span>{f.label}</span>
              <input
                type="number"
                required
                min={f.min}
                max={f.key === "matches_per_week" ? Math.min(f.max, maxMatches) : f.max}
                disabled={locked}
                value={form[f.key]}
                onChange={(e) => setForm({ ...form, [f.key]: Number(e.target.value) })}
              />
              <small className={f.key === "matches_per_week" && tooManyMatches ? "error" : "muted"}>
                {locked
                  ? "Fixed: matches have been played."
                  : f.key === "matches_per_week" && tooManyMatches
                    ? `At most ${plural(maxMatches, "match", "matches")} with ${form.num_teams} teams (one against each other team).`
                    : f.help}
              </small>
            </label>
          );
        })}
      </div>

      <label className="field points-field">
        <span>Points to win</span>
        <select
          disabled={lockedAfterPlay}
          value={form.points_to_win}
          onChange={(e) => setForm({ ...form, points_to_win: Number(e.target.value) as PointsToWin })}
        >
          {POINTS_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p} points
            </option>
          ))}
        </select>
        <small className="muted">
          {lockedAfterPlay
            ? "Fixed: matches have been played."
            : `Games are first to ${n}, win by 2 (e.g. ${exampleScores}).`}
        </small>
      </label>

      <label className="toggle">
        <input
          type="checkbox"
          checked={form.use_team_names}
          onChange={(e) => setForm({ ...form, use_team_names: e.target.checked })}
        />
        <span>
          <strong>Use team names</strong>
          <small className="muted">
            {form.use_team_names
              ? "Each team gets a name, entered with its players."
              : "Teams are shown by their players' names, e.g. “Alex & Sam”."}
          </small>
        </span>
      </label>

      <div className="card summary" aria-live="polite">
        <p>
          Each team plays {plural(form.matches_per_week, "match", "matches")} a week
          {preview && (
            <>
              {" "}
              over {plural(preview.rounds_per_week, "round")} ({plural(preview.games_per_week, "game")} a week,{" "}
              {plural(preview.games_per_week * form.num_weeks, "game")} in the season)
            </>
          )}
          . Up to {plural(gamesPerRound, "game")} per round, played in {plural(wavesPerRound, "wave")} on{" "}
          {plural(form.num_courts, "court")}.
        </p>
        {preview?.has_catch_up_round && (
          <p>
            With an odd number of teams, one team sits out each round; the last round of the week is a
            catch-up round where those teams play each other.
          </p>
        )}
        {preview?.teams_short_per_week ? (
          <p>
            {form.num_teams} teams × {form.matches_per_week} matches is odd, so each week one team plays a
            match fewer (rotating between teams).
          </p>
        ) : null}
        {preview && form.num_teams > 2 && (
          <p>
            Over the season each pair of teams meets{" "}
            {preview.min_meetings === preview.max_meetings
              ? plural(preview.min_meetings, "time")
              : `${preview.min_meetings}–${preview.max_meetings} times`}
            .
          </p>
        )}
        <p>
          Games are first to {form.points_to_win}, win by 2 (e.g. {exampleScores}); no ties.
        </p>
      </div>

      <div>
        <button type="submit" disabled={saving || tooManyMatches}>
          {saving ? "Saving…" : "Next: teams & players →"}
        </button>
      </div>
    </form>
  );
}
