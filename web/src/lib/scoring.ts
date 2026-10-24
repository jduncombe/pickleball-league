// Pickleball game-score rules: first to N points, win by 2. Mirrors
// api/app/scoring.py (the API enforces them; this is for instant feedback).

import { a, term } from "./terms";

export type ScoreField = "score_a" | "score_b";

export interface ScoreProblem {
  message: string;
  /** Which score(s) are most likely wrong. */
  fields: ScoreField[];
}

/** A valid final score in which the losing side has `loser` points. */
function exampleWin(n: number, loser: number): string {
  return loser <= n - 2 ? `${n}-${loser}` : `${loser + 2}-${loser}`;
}

export function checkScore(scoreA: number, scoreB: number, pointsToWin: number): ScoreProblem | null {
  const n = pointsToWin;
  const high = Math.max(scoreA, scoreB);
  const low = Math.min(scoreA, scoreB);
  const entered = `${scoreA}-${scoreB}`;

  if (scoreA === scoreB) {
    return {
      message: `${entered} is a tie: there are no ties, play continues until one side leads by 2 (e.g. ${exampleWin(n, low)})`,
      fields: ["score_a", "score_b"],
    };
  }
  const [winner, loser]: ScoreField[] = scoreA > scoreB ? ["score_a", "score_b"] : ["score_b", "score_a"];

  if (high < n) {
    return {
      message: `${entered} isn't finished: the winner needs at least ${n} points (e.g. ${exampleWin(n, low)})`,
      fields: [winner],
    };
  }
  if (high - low < 2) {
    return {
      message: `${entered} isn't finished: ${a("game")} must be won by 2, so play continues (e.g. ${exampleWin(n, low)})`,
      fields: [loser],
    };
  }
  if (high > n && high - low > 2) {
    return {
      message: `${entered} isn't possible: the ${term("game")} ends as soon as one side has ${n}+ points and leads by 2 (e.g. ${exampleWin(n, low)})`,
      fields: [winner],
    };
  }
  return null;
}
