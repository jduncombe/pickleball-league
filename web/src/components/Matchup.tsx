import type { Match } from "@/lib/types";
import { TeamName } from "./TeamName";

export function Matchup({ match, showDupr = false }: { match: Match; showDupr?: boolean }) {
  const done = match.status === "completed";
  const aWon = done && (match.score_a ?? 0) > (match.score_b ?? 0);
  return (
    <span className="matchup">
      <TeamName team={match.team_a} showDupr={showDupr} className={done && aWon ? "winner" : ""} />
      <span className="vs">{done ? `${match.score_a} – ${match.score_b}` : "vs"}</span>
      <TeamName team={match.team_b} showDupr={showDupr} className={done && !aWon ? "winner" : ""} />
    </span>
  );
}
