"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Match, TeamRef } from "@/lib/types";
import { TeamName } from "./TeamName";

/**
 * Score entry for a match. Calls `onSaved` after a successful save.
 * "inline": two boxes in a row (schedule list). "board": a team per row,
 * name beside its box (live court cards).
 */
export function ScoreForm({
  match,
  onSaved,
  layout = "inline",
  showDupr = false,
}: {
  match: Match;
  onSaved: () => void;
  layout?: "inline" | "board";
  showDupr?: boolean;
}) {
  const [a, setA] = useState(match.score_a?.toString() ?? "");
  const [b, setB] = useState(match.score_b?.toString() ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.recordResult(match.id, Number(a), Number(b));
      setError(null);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  const scoreInput = (team: TeamRef, value: string, set: (v: string) => void) => (
    <input
      aria-label={`${team.display_name} score`}
      type="number"
      inputMode="numeric"
      min={0}
      max={99}
      required
      value={value}
      onChange={(e) => set(e.target.value)}
    />
  );
  const saveLabel = match.status === "completed" ? "Update" : "Save";

  if (layout === "board") {
    // One row per team, name beside its score box, so the two line up.
    return (
      <form className="scoreboard" onSubmit={submit}>
        <TeamName team={match.team_a} showDupr={showDupr} className="team" />
        {scoreInput(match.team_a, a, setA)}
        <TeamName team={match.team_b} showDupr={showDupr} className="team" />
        {scoreInput(match.team_b, b, setB)}
        <button type="submit" disabled={saving}>
          {saveLabel} score
        </button>
        {error && <span className="error inline">{error}</span>}
      </form>
    );
  }

  return (
    <form className="score-form" onSubmit={submit}>
      {scoreInput(match.team_a, a, setA)}
      <span>–</span>
      {scoreInput(match.team_b, b, setB)}
      <button type="submit" disabled={saving}>
        {saveLabel}
      </button>
      {error && <span className="error inline">{error}</span>}
    </form>
  );
}
