// Thin typed client for the Python API. Requests go to the same-origin
// /api proxy (src/app/api/[...path]/route.ts), which forwards to API_URL.

import type {
  Dashboard,
  League,
  LeagueCreate,
  Match,
  Player,
  PlayerInput,
  StandingRow,
  Team,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((d: { msg: string }) => d.msg).join("; ")
            : message;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  // Leagues
  listLeagues: () => request<League[]>("/leagues"),
  getLeague: (id: number) => request<League>(`/leagues/${id}`),
  createLeague: (body: LeagueCreate) =>
    request<League>("/leagues", { method: "POST", body: json(body) }),
  updateLeague: (id: number, body: Partial<Pick<League, "name" | "num_courts" | "current_week">>) =>
    request<League>(`/leagues/${id}`, { method: "PATCH", body: json(body) }),
  dashboard: (id: number, week?: number) =>
    request<Dashboard>(`/leagues/${id}/dashboard${week ? `?week=${week}` : ""}`),
  standings: (id: number) => request<StandingRow[]>(`/leagues/${id}/standings`),

  // Teams & players
  listTeams: (leagueId: number) => request<Team[]>(`/leagues/${leagueId}/teams`),
  renameTeam: (teamId: number, name: string) =>
    request<Team>(`/teams/${teamId}`, { method: "PATCH", body: json({ name }) }),
  addPlayer: (teamId: number, body: PlayerInput) =>
    request<Player>(`/teams/${teamId}/players`, { method: "POST", body: json(body) }),
  updatePlayer: (playerId: number, body: Partial<PlayerInput>) =>
    request<Player>(`/players/${playerId}`, { method: "PATCH", body: json(body) }),
  deletePlayer: (playerId: number) =>
    request<void>(`/players/${playerId}`, { method: "DELETE" }),

  // Matches
  listMatches: (leagueId: number, week?: number) =>
    request<Match[]>(`/leagues/${leagueId}/matches${week ? `?week=${week}` : ""}`),
  startMatch: (matchId: number, court?: number) =>
    request<Match>(`/matches/${matchId}/start`, { method: "POST", body: json({ court }) }),
  cancelMatch: (matchId: number) =>
    request<Match>(`/matches/${matchId}/cancel`, { method: "POST" }),
  recordResult: (matchId: number, score_a: number, score_b: number) =>
    request<Match>(`/matches/${matchId}/result`, {
      method: "PUT",
      body: json({ score_a, score_b }),
    }),
};
