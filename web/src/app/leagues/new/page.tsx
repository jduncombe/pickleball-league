"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorBanner } from "@/components/Status";
import { api } from "@/lib/api";
import { leagueHref } from "@/lib/routes";
import { DUPR_ID_PATTERN, DUPR_ID_TITLE, teamDisplayName } from "@/lib/teams";
import type { LeagueCreate, TeamSetup } from "@/lib/types";

type Settings = Omit<LeagueCreate, "teams">;

const FIELDS: { key: Exclude<keyof Settings, "name">; label: string; min: number; max: number; help: string }[] = [
  { key: "num_teams", label: "Number of teams", min: 2, max: 64, help: "Enter each team below." },
  { key: "num_weeks", label: "Number of weeks", min: 1, max: 52, help: "Length of the season." },
  { key: "rounds_per_week", label: "Rounds per week", min: 1, max: 20, help: "Each team plays at most once per round." },
  { key: "num_courts", label: "Courts in use", min: 1, max: 50, help: "Limits how many matches run at once." },
];

const PLAYERS_PER_TEAM = 2; // doubles; more can be added per team

interface PlayerDraft {
  name: string;
  email: string;
  dupr_id: string;
}

interface TeamDraft {
  name: string;
  players: PlayerDraft[];
}

const blankPlayer = (): PlayerDraft => ({ name: "", email: "", dupr_id: "" });
const blankTeam = (): TeamDraft => ({
  name: "",
  players: Array.from({ length: PLAYERS_PER_TEAM }, blankPlayer),
});

const clampTeams = (count: number) => (Number.isFinite(count) ? Math.min(Math.max(count, 0), 64) : 0);

/**
 * Make sure there are at least `count` drafts. Never shrinks: lowering the
 * team count (even briefly, e.g. typing "12" passes through "1") only hides
 * the extra teams, so nothing typed is lost.
 */
function ensureTeams(teams: TeamDraft[], count: number): TeamDraft[] {
  const n = clampTeams(count);
  return n <= teams.length ? teams : [...teams, ...Array.from({ length: n - teams.length }, blankTeam)];
}

function toSetup(team: TeamDraft): TeamSetup {
  return {
    name: team.name.trim() || null,
    players: team.players
      .filter((p) => p.name.trim())
      .map((p) => ({ name: p.name.trim(), email: p.email.trim() || null, dupr_id: p.dupr_id.trim() || null })),
  };
}

export default function NewLeaguePage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings>({
    name: "",
    num_teams: 8,
    num_weeks: 8,
    rounds_per_week: 3,
    num_courts: 4,
  });
  const [drafts, setDrafts] = useState<TeamDraft[]>(() => ensureTeams([], 8));
  const teams = drafts.slice(0, clampTeams(settings.num_teams));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const matchesPerRound = Math.floor(settings.num_teams / 2);
  const wavesPerRound = Math.ceil(matchesPerRound / Math.max(settings.num_courts, 1));
  const totalMatches = matchesPerRound * settings.num_weeks * settings.rounds_per_week;

  function setSetting(key: keyof Settings, value: string | number) {
    setSettings({ ...settings, [key]: value });
    if (key === "num_teams") setDrafts((current) => ensureTeams(current, Number(value)));
  }

  function updateTeam(index: number, change: (team: TeamDraft) => TeamDraft) {
    setDrafts((current) => current.map((t, i) => (i === index ? change(t) : t)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const league = await api.createLeague({ ...settings, teams: teams.map(toSetup) });
      router.push(leagueHref("/league", league.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSaving(false);
    }
  }

  return (
    <form className="stack setup" onSubmit={submit}>
      <h1>New league</h1>

      <section className="stack narrow">
        <label className="field">
          <span>League name</span>
          <input
            required
            maxLength={120}
            value={settings.name}
            onChange={(e) => setSetting("name", e.target.value)}
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
                value={settings[f.key]}
                onChange={(e) => setSetting(f.key, Number(e.target.value))}
              />
              <small className="muted">{f.help}</small>
            </label>
          ))}
        </div>

        <p className="card summary">
          {matchesPerRound} matches per round
          {settings.num_teams % 2 === 1 && " (one team sits out each round)"} · {totalMatches} matches
          in the season · each round plays in {wavesPerRound} wave{wavesPerRound === 1 ? "" : "s"} on{" "}
          {settings.num_courts} court{settings.num_courts === 1 ? "" : "s"}.
        </p>
      </section>

      <section className="stack">
        <div>
          <h2>Teams</h2>
          <p className="muted">
            Team names are optional: a team without one is shown by its players&apos; names. Teams
            are set up once, here; afterwards you can rename them and correct players, but not add
            or remove teams.
          </p>
        </div>
        <div className="grid wide">
          {teams.map((team, i) => (
            <TeamFields key={i} index={i} team={team} onChange={(change) => updateTeam(i, change)} />
          ))}
        </div>
      </section>

      <ErrorBanner message={error} />
      <div>
        <button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Create league & schedule"}
        </button>
      </div>
    </form>
  );
}

function TeamFields({
  index,
  team,
  onChange,
}: {
  index: number;
  team: TeamDraft;
  onChange: (change: (team: TeamDraft) => TeamDraft) => void;
}) {
  const position = index + 1;
  const shownAs = teamDisplayName(team.name, team.players.map((p) => p.name), position);

  const setPlayer = (j: number, field: keyof PlayerDraft, value: string) =>
    onChange((t) => ({ ...t, players: t.players.map((p, k) => (k === j ? { ...p, [field]: value } : p)) }));

  return (
    <fieldset className="card team-setup">
      <legend className="sr-only">Team {position}</legend>
      <div className="card-head">
        <strong>Team {position}</strong>
        <span className="muted" aria-live="polite">
          Shown as: {shownAs}
        </span>
      </div>
      <input
        aria-label={`Team ${position} name (optional)`}
        placeholder="Team name (optional)"
        maxLength={120}
        value={team.name}
        onChange={(e) => onChange((t) => ({ ...t, name: e.target.value }))}
      />
      {team.players.map((p, j) => {
        // A row with any detail filled in needs a name; fully blank rows are skipped.
        const used = Boolean(p.email.trim() || p.dupr_id.trim());
        return (
          <div key={j} className="player-row">
            <input
              aria-label={`Team ${position} player ${j + 1} name`}
              placeholder={`Player ${j + 1}`}
              required={used}
              maxLength={120}
              value={p.name}
              onChange={(e) => setPlayer(j, "name", e.target.value)}
            />
            <input
              aria-label={`Team ${position} player ${j + 1} DUPR ID`}
              placeholder="DUPR ID"
              pattern={DUPR_ID_PATTERN}
              title={DUPR_ID_TITLE}
              value={p.dupr_id}
              onChange={(e) => setPlayer(j, "dupr_id", e.target.value)}
            />
            <input
              aria-label={`Team ${position} player ${j + 1} email`}
              type="email"
              placeholder="Email"
              value={p.email}
              onChange={(e) => setPlayer(j, "email", e.target.value)}
            />
            <button
              type="button"
              className="link danger"
              aria-label={`Remove team ${position} player ${j + 1}`}
              onClick={() => onChange((t) => ({ ...t, players: t.players.filter((_, k) => k !== j) }))}
            >
              ✕
            </button>
          </div>
        );
      })}
      <div>
        <button
          type="button"
          className="secondary small"
          onClick={() => onChange((t) => ({ ...t, players: [...t.players, blankPlayer()] }))}
        >
          + Player
        </button>
      </div>
    </fieldset>
  );
}
