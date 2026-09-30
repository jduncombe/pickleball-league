import type { Match } from "@/lib/types";

export function Matchup({ match }: { match: Match }) {
  const done = match.status === "completed";
  const aWon = done && (match.score_a ?? 0) > (match.score_b ?? 0);
  return (
    <span className="matchup">
      <strong className={done && aWon ? "winner" : ""}>{match.team_a.name}</strong>
      <span className="vs">{done ? `${match.score_a} – ${match.score_b}` : "vs"}</span>
      <strong className={done && !aWon ? "winner" : ""}>{match.team_b.name}</strong>
    </span>
  );
}
