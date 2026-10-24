"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import { type ScoreField, checkScore } from "@/lib/scoring";
import type { Match, TeamRef } from "@/lib/types";
import { TeamName } from "./TeamName";

/**
 * Score entry for a match. Calls `onSaved` after a successful save.
 * "inline": two boxes in a row (schedule list). "board": a team per row,
 * name beside its box (live court cards).
 *
 * Scores are checked against the league's rules (first to `pointsToWin`, win
 * by 2) before saving; the box that is most likely wrong is highlighted.
 */
export function ScoreForm({
  match,
  pointsToWin,
  onSaved,
  layout = "inline",
  showDupr = false,
}: {
  match: Match;
  pointsToWin: number;
  onSaved: () => void;
  layout?: "inline" | "board";
  showDupr?: boolean;
}) {
  const [a, setA] = useState(match.score_a?.toString() ?? "");
  const [b, setB] = useState(match.score_b?.toString() ?? "");
  const [error, setError] = useState<string | null>(null);
  const [invalid, setInvalid] = useState<ScoreField[]>([]);
  const [saving, setSaving] = useState(false);

  function fail(message: string, fields: ScoreField[]) {
    setError(message);
    setInvalid(fields);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const blank = (["score_a", "score_b"] as const).filter((f) => (f === "score_a" ? a : b).trim() === "");
    if (blank.length) return fail("Enter both scores", [...blank]);
    const problem = checkScore(Number(a), Number(b), pointsToWin);
    if (problem) return fail(problem.message, problem.fields);

    setSaving(true);
    try {
      await api.recordResult(match.id, Number(a), Number(b));
      setError(null);
      setInvalid([]);
      onSaved();
    } catch (err) {
      const fields =
        err instanceof ApiError
          ? err.fields.filter((f): f is ScoreField => f === "score_a" || f === "score_b")
          : [];
      fail(err instanceof Error ? err.message : String(err), fields);
    } finally {
      setSaving(false);
    }
  }

  const scoreInput = (field: ScoreField, team: TeamRef, value: string, set: (v: string) => void) => {
    const bad = invalid.includes(field);
    return (
      <input
        aria-label={`${team.display_name} score`}
        aria-invalid={bad || undefined}
        aria-describedby={bad ? `score-error-${match.id}` : undefined}
        className={bad ? "invalid" : undefined}
        type="number"
        inputMode="numeric"
        min={0}
        max={99}
        required
        value={value}
        onChange={(e) => {
          set(e.target.value);
          setInvalid((current) => current.filter((f) => f !== field));
        }}
      />
    );
  };
  const saveLabel = match.status === "completed" ? "Update" : "Save";
  const errorText = error && (
    <span id={`score-error-${match.id}`} className="error inline" role="alert">
      {error}
    </span>
  );

  if (layout === "board") {
    // One row per team, name beside its score box, so the two line up.
    return (
      <form className="scoreboard" onSubmit={submit} noValidate>
        <TeamName team={match.team_a} showDupr={showDupr} className="team" />
        {scoreInput("score_a", match.team_a, a, setA)}
        <TeamName team={match.team_b} showDupr={showDupr} className="team" />
        {scoreInput("score_b", match.team_b, b, setB)}
        <button type="submit" disabled={saving}>
          {saveLabel} score
        </button>
        {errorText}
      </form>
    );
  }

  return (
    <form className="score-form" onSubmit={submit} noValidate>
      {scoreInput("score_a", match.team_a, a, setA)}
      <span>–</span>
      {scoreInput("score_b", match.team_b, b, setB)}
      <button type="submit" disabled={saving}>
        {saveLabel}
      </button>
      {errorText}
    </form>
  );
}
