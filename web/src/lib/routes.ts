// League pages take the league id as a query parameter (/league/?id=3) rather
// than a path segment, so the site can be a fully static export on S3.

export type LeaguePath = "/league" | "/league/teams" | "/league/matches";

export function leagueHref(path: LeaguePath, id: number): string {
  return `${path}/?id=${id}`;
}
