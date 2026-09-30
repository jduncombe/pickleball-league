"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorBanner } from "@/components/Status";
import { api } from "@/lib/api";
import type { LeagueCreate } from "@/lib/types";

const FIELDS: { key: Exclude<keyof LeagueCreate, "name">; label: string; min: number; max: number; help: string }[] = [
  { key: "num_teams", label: "Number of teams", min: 2, max: 64, help: "Placeholder teams are created; rename them next." },
  { key: "num_weeks", label: "Number of weeks", min: 1, max: 52, help: "Length of the season." },
  { key: "rounds_per_week", label: "Rounds per week", min: 1, max: 20, help: "Each team plays at most once per round." },
  { key: "num_courts", label: "Courts in use", min: 1, max: 50, help: "Limits how many matches run at once." },
];

export default function NewLeaguePage() {
  const router = useRouter();
  const [form, setForm] = useState<LeagueCreate>({
    name: "",
    num_teams: 8,
    num_weeks: 8,
    rounds_per_week: 3,
    num_courts: 4,
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const matchesPerRound = Math.floor(form.num_teams / 2);
  const wavesPerRound = Math.ceil(matchesPerRound / Math.max(form.num_courts, 1));
  const totalMatches = matchesPerRound * form.rounds_per_week * form.num_weeks;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const league = await api.createLeague(form);
      router.push(`/leagues/${league.id}/teams`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  return (
    <form className="stack narrow" onSubmit={submit}>
      <h1>New league</h1>
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
        {FIELDS.map((f) => (
          <label key={f.key} className="field">
            <span>{f.label}</span>
            <input
              type="number"
              required
              min={f.min}
              max={f.max}
              value={form[f.key]}
              onChange={(e) => setForm({ ...form, [f.key]: Number(e.target.value) })}
            />
            <small className="muted">{f.help}</small>
          </label>
        ))}
      </div>

      <p className="card summary">
        {matchesPerRound} matches per round
        {form.num_teams % 2 === 1 && " (one team sits out each round)"} · {totalMatches} matches
        in the season · each round plays in {wavesPerRound} wave{wavesPerRound === 1 ? "" : "s"} on{" "}
        {form.num_courts} court{form.num_courts === 1 ? "" : "s"}.
      </p>

      <div>
        <button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Create league & schedule"}
        </button>
      </div>
    </form>
  );
}
