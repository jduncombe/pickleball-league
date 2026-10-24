"use client";

import { useState } from "react";
import { DUPR_ID_PATTERN, DUPR_ID_TITLE, teamDisplayName } from "@/lib/teams";
import type { League, Team, TeamSetup } from "@/lib/types";
import { ErrorBanner } from "../Status";

const MIN_PLAYER_ROWS = 2; // doubles; more can be added per team

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

function toDraft(team: Team): TeamDraft {
  const players = team.players.map((p) => ({ name: p.name, email: p.email ?? "", dupr_id: p.dupr_id ?? "" }));
  while (players.length < MIN_PLAYER_ROWS) players.push(blankPlayer());
  return { name: team.name ?? "", players };
}

function toSetup(team: TeamDraft): TeamSetup {
  return {
    name: team.name.trim() || null,
    players: team.players
      .filter((p) => p.name.trim())
      .map((p) => ({ name: p.name.trim(), email: p.email.trim() || null, dupr_id: p.dupr_id.trim() || null })),
  };
}

export type TeamsAction = "back" | "save" | "create";

/**
 * Setup step 2: players (and team names, if the league uses them) for every
 * team. `onAction` saves the teams and then goes back, stays, or creates the
 * league.
 */
export function TeamsForm({
  league,
  teams,
  onAction,
}: {
  league: League;
  teams: Team[];
  onAction: (action: TeamsAction, teams: TeamSetup[]) => Promise<void>;
}) {
  const [drafts, setDrafts] = useState<TeamDraft[]>(() => teams.map(toDraft));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<TeamsAction | null>(null);
  const [saved, setSaved] = useState(false);

  const isRecreate = league.created_league_at !== null;

  function updateTeam(index: number, change: (team: TeamDraft) => TeamDraft) {
    setSaved(false);
    setDrafts((current) => current.map((t, i) => (i === index ? change(t) : t)));
  }

  // Drafts can be saved incomplete; "Create the league" is a form submit, so
  // the browser checks required fields first (and the API validates again).
  async function run(action: TeamsAction) {
    setBusy(action);
    try {
      await onAction(action, drafts.map(toSetup));
      setError(null);
      setSaved(action === "save");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        run("create");
      }}
    >
      <p className="muted">
        {league.use_team_names
          ? "Enter each team's name and players."
          : "Enter each team's players; teams will be shown by their players' names."}{" "}
        Players are fixed once the league is created (use <em>Edit setup</em> to change them later).
      </p>

      <div className="grid wide">
        {drafts.map((team, i) => (
          <TeamFields
            key={i}
            position={i + 1}
            team={team}
            useTeamNames={league.use_team_names}
            onChange={(change) => updateTeam(i, change)}
          />
        ))}
      </div>

      <ErrorBanner message={error} />
      <div className="actions">
        <button type="button" className="secondary" disabled={busy !== null} onClick={() => run("back")}>
          ← Back to basics
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy !== null}
          onClick={() => run("save")}
        >
          {busy === "save" ? "Saving…" : saved ? "Saved" : "Save draft"}
        </button>
        <button type="submit" disabled={busy !== null}>
          {busy === "create" ? "Creating…" : isRecreate ? "Save & resume league" : "Create the league"}
        </button>
      </div>
    </form>
  );
}

function TeamFields({
  position,
  team,
  useTeamNames,
  onChange,
}: {
  position: number;
  team: TeamDraft;
  useTeamNames: boolean;
  onChange: (change: (team: TeamDraft) => TeamDraft) => void;
}) {
  const shownAs = teamDisplayName(useTeamNames, team.name, team.players.map((p) => p.name), position);
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
      {useTeamNames && (
        <input
          aria-label={`Team ${position} name`}
          placeholder="Team name"
          required
          maxLength={120}
          value={team.name}
          onChange={(e) => onChange((t) => ({ ...t, name: e.target.value }))}
        />
      )}
      {team.players.map((p, j) => {
        // The first player is required; other rows need a name only if partly filled in.
        const required = j === 0 || Boolean(p.email.trim() || p.dupr_id.trim());
        return (
          <div key={j} className="player-row">
            <input
              aria-label={`Team ${position} player ${j + 1} name`}
              placeholder={`Player ${j + 1}`}
              required={required}
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
              disabled={team.players.length <= 1}
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
