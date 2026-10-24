// League pages take the league id as a query parameter (/league/?id=3) rather
// than a path segment, so the site can be a fully static export on S3.

export type LeaguePath = "/league" | "/league/teams" | "/league/matches" | "/league/setup";

export type SetupStep = "basics" | "players";

export function leagueHref(path: LeaguePath, id: number): string {
  return `${path}/?id=${id}`;
}

export function setupHref(id: number, step: SetupStep): string {
  return `/league/setup/?id=${id}&step=${step}`;
}
