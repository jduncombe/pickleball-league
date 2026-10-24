"use client";

import { useState } from "react";
import { type LeagueBasics, POINTS_OPTIONS, type PointsToWin } from "@/lib/types";
import { ErrorBanner } from "../Status";

type NumberField = "num_teams" | "num_weeks" | "rounds_per_week" | "num_courts";

const FIELDS: { key: NumberField; label: string; min: number; max: number; help: string; schedule: boolean }[] = [
  { key: "num_teams", label: "Number of teams", min: 2, max: 64, help: "Players are entered on the next step.", schedule: true },
  { key: "num_weeks", label: "Number of weeks", min: 1, max: 52, help: "Length of the season.", schedule: true },
  { key: "rounds_per_week", label: "Rounds per week", min: 1, max: 20, help: "Each team plays at most once per round.", schedule: true },
  { key: "num_courts", label: "Courts in use", min: 1, max: 50, help: "Limits how many matches run at once.", schedule: false },
];

export const DEFAULT_BASICS: LeagueBasics = {
  name: "",
  num_teams: 8,
  num_weeks: 8,
  rounds_per_week: 3,
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

  const matchesPerRound = Math.floor(form.num_teams / 2);
  const wavesPerRound = Math.ceil(matchesPerRound / Math.max(form.num_courts, 1));
  const totalMatches = matchesPerRound * form.rounds_per_week * form.num_weeks;

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
                max={f.max}
                disabled={locked}
                value={form[f.key]}
                onChange={(e) => setForm({ ...form, [f.key]: Number(e.target.value) })}
              />
              <small className="muted">{locked ? "Fixed: matches have been played." : f.help}</small>
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
            : `Games are first to ${form.points_to_win}, win by 2 (e.g. ${form.points_to_win}-${form.points_to_win - 2} or ${form.points_to_win + 1}-${form.points_to_win - 1}).`}
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

      <p className="card summary">
        {matchesPerRound} matches per round
        {form.num_teams % 2 === 1 && " (one team sits out each round)"} · {totalMatches} matches in
        the season · each round plays in {wavesPerRound} wave{wavesPerRound === 1 ? "" : "s"} on{" "}
        {form.num_courts} court{form.num_courts === 1 ? "" : "s"}.
      </p>

      <div>
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Next: teams & players →"}
        </button>
      </div>
    </form>
  );
}
