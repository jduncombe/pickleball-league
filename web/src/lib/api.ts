// Thin typed client for the Python API.
//
// By default requests go to same-origin /api, which is routed to the API by
// CloudFront in AWS, nginx in docker-compose, and a dev-server rewrite under
// `npm run dev` (see next.config.ts). NEXT_PUBLIC_API_URL overrides this at
// build time, e.g. to call the API directly (needs CORS_ORIGINS on the API).

import type { Dashboard, League, LeagueBasics, Match, StandingRow, Team, TeamSetup } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Request fields a validation error points at (e.g. "score_b"). */
    public fields: string[] = [],
  ) {
    super(message);
  }
}

type ValidationError = { loc?: (string | number)[]; msg: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = res.statusText;
    let fields: string[] = [];
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        const errors = body.detail as ValidationError[];
        message = [...new Set(errors.map((d) => d.msg))].join("; ");
        fields = errors.map((d) => String(d.loc?.at(-1) ?? ""));
      }
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, message, fields);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  // Leagues
  listLeagues: () => request<League[]>("/leagues"),
  getLeague: (id: number) => request<League>(`/leagues/${id}`),
  setCurrentWeek: (id: number, current_week: number) =>
    request<League>(`/leagues/${id}`, { method: "PATCH", body: json({ current_week }) }),
  dashboard: (id: number, week?: number) =>
    request<Dashboard>(`/leagues/${id}/dashboard${week ? `?week=${week}` : ""}`),
  standings: (id: number) => request<StandingRow[]>(`/leagues/${id}/standings`),
  listTeams: (leagueId: number) => request<Team[]>(`/leagues/${leagueId}/teams`),

  // Setup (teams and players can only be changed while a league is in setup)
  createLeague: (body: LeagueBasics) =>
    request<League>("/leagues", { method: "POST", body: json(body) }),
  updateBasics: (id: number, body: LeagueBasics) =>
    request<League>(`/leagues/${id}/setup`, { method: "PUT", body: json(body) }),
  updateTeams: (id: number, teams: TeamSetup[]) =>
    request<Team[]>(`/leagues/${id}/teams`, { method: "PUT", body: json({ teams }) }),
  /** "Create the league": validate setup, build the schedule, make it active. */
  finalizeSetup: (id: number) => request<League>(`/leagues/${id}/finalize`, { method: "POST" }),
  /** "Edit setup": put an active league back into setup. */
  editSetup: (id: number) => request<League>(`/leagues/${id}/edit`, { method: "POST" }),

  // Matches
  listMatches: (leagueId: number, week?: number) =>
    request<Match[]>(`/leagues/${leagueId}/matches${week ? `?week=${week}` : ""}`),
  startMatch: (matchId: number, court?: number) =>
    request<Match>(`/matches/${matchId}/start`, { method: "POST", body: json({ court }) }),
  cancelMatch: (matchId: number) =>
    request<Match>(`/matches/${matchId}/cancel`, { method: "POST" }),
  /** Lock a completed match's result; it can't be changed afterwards. */
  verifyMatch: (matchId: number) => request<Match>(`/matches/${matchId}/verify`, { method: "POST" }),
  recordResult: (matchId: number, score_a: number, score_b: number) =>
    request<Match>(`/matches/${matchId}/result`, {
      method: "PUT",
      body: json({ score_a, score_b }),
    }),
};
