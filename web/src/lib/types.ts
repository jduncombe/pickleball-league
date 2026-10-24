// Mirrors the response schemas in api/app/schemas.py.

export type MatchStatus = "scheduled" | "in_progress" | "completed";

export interface League {
  id: number;
  name: string;
  num_teams: number;
  num_weeks: number;
  rounds_per_week: number;
  num_courts: number;
  current_week: number;
  created_at: string;
}

export interface LeagueCreate {
  name: string;
  num_teams: number;
  num_weeks: number;
  rounds_per_week: number;
  num_courts: number;
  /** One entry per team, in order. Teams are only created here, at setup. */
  teams?: TeamSetup[];
}

export interface TeamSetup {
  /** Optional; unnamed teams are shown by their players' names. */
  name?: string | null;
  players: PlayerInput[];
}

export interface Player {
  id: number;
  team_id: number;
  name: string;
  email: string | null;
  dupr_id: string | null;
  dupr_rating: number | null;
}

export interface PlayerInput {
  name: string;
  email?: string | null;
  dupr_id?: string | null;
}

export interface TeamRef {
  id: number;
  name: string | null;
  /** name, else the players' names ("Alex & Sam"), else "Team N". Use this for display. */
  display_name: string;
}

export interface Team extends TeamRef {
  league_id: number;
  position: number;
  players: Player[];
}

export interface Match {
  id: number;
  league_id: number;
  week: number;
  round: number;
  status: MatchStatus;
  court: number | null;
  team_a: TeamRef;
  team_b: TeamRef;
  score_a: number | null;
  score_b: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Dashboard {
  league: League;
  week: number;
  free_courts: number[];
  in_progress: Match[];
  available: Match[];
  waiting: Match[];
  completed_count: number;
  total_count: number;
}

export interface StandingRow {
  team: TeamRef;
  played: number;
  wins: number;
  losses: number;
  points_for: number;
  points_against: number;
  point_diff: number;
}
