"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Match } from "@/lib/types";

/** Inline score entry for a match. Calls `onSaved` after a successful save. */
export function ScoreForm({ match, onSaved }: { match: Match; onSaved: () => void }) {
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

  return (
    <form className="score-form" onSubmit={submit}>
      <input
        aria-label={`${match.team_a.name} score`}
        type="number"
        min={0}
        max={99}
        required
        value={a}
        onChange={(e) => setA(e.target.value)}
      />
      <span>–</span>
      <input
        aria-label={`${match.team_b.name} score`}
        type="number"
        min={0}
        max={99}
        required
        value={b}
        onChange={(e) => setB(e.target.value)}
      />
      <button type="submit" disabled={saving}>
        {match.status === "completed" ? "Update" : "Save"}
      </button>
      {error && <span className="error inline">{error}</span>}
    </form>
  );
}
