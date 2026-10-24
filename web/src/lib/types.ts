// Mirrors the response schemas in api/app/schemas.py.

export type MatchStatus = "scheduled" | "in_progress" | "completed";

/** "setup": basics/teams/players being entered or edited. "active": created, playable. */
export type LeagueStatus = "setup" | "active";

export const POINTS_OPTIONS = [11, 15, 21] as const;
export type PointsToWin = (typeof POINTS_OPTIONS)[number];

/** Setup step 1. */
export interface LeagueBasics {
  name: string;
  num_teams: number;
  num_weeks: number;
  /** Matches each team plays per week (at most num_teams - 1). */
  matches_per_week: number;
  num_courts: number;
  /** Games are first to this many points, win by 2. */
  points_to_win: PointsToWin;
  /** When false, teams are shown by their players' names. */
  use_team_names: boolean;
}

export interface League extends LeagueBasics {
  id: number;
  status: LeagueStatus;
  /** When the league was first created (setup finalised); null until then. */
  created_league_at: string | null;
  /** Once true, num_teams / num_weeks / matches_per_week / points_to_win can't change. */
  has_played_matches: boolean;
  current_week: number;
  created_at: string;
}

/** Setup step 2, one per team in position order. */
export interface TeamSetup {
  name: string | null;
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
  /** name (if the league uses team names), else the players' names ("Alex & Sam"), else "Team N". */
  display_name: string;
  /** Every player on the team has a DUPR ID. */
  dupr_ready: boolean;
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
  /** Set once the result is verified; the score is then locked. */
  verified_at: string | null;
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

/** Shape of the schedule some setup basics would produce (GET /schedule-preview). */
export interface SchedulePreview {
  rounds_per_week: number;
  games_per_week: number;
  /** Odd team count: each week ends with a round for the teams that sat out. */
  has_catch_up_round: boolean;
  /** 1 when teams x matches is odd: one team per week plays a match fewer. */
  teams_short_per_week: number;
  /** Fewest and most times any two teams meet over the season. */
  min_meetings: number;
  max_meetings: number;
}
