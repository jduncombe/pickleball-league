import { Term, term } from "./terms";

// Mirrors Team.display_name in api/app/models.py, for previews while editing
// setup. Anything already saved should use the API's display_name instead.

export function teamDisplayName(
  useTeamNames: boolean,
  name: string | null | undefined,
  playerNames: string[],
  position: number,
): string {
  if (useTeamNames && name?.trim()) return name.trim();
  const names = playerNames.map((n) => n.trim()).filter(Boolean);
  if (names.length === 0) return `${Term("team")} ${position}`;
  if (names.length === 1) return names[0];
  return `${names.slice(0, -1).join(", ")} & ${names[names.length - 1]}`;
}

// Matches DUPR_ID_PATTERN in api/app/schemas.py.
export const DUPR_ID_PATTERN = "[A-Za-z0-9]{4,12}";
export const DUPR_ID_TITLE = `4–12 letters or digits, as shown on the ${term("player")}'s ${term("ratingSystem")} profile`;
