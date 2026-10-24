import type { SetupStep } from "@/lib/routes";
import { Term, term } from "@/lib/terms";

const STEPS: { step: SetupStep; label: string }[] = [
  { step: "basics", label: `${Term("league")} basics` },
  { step: "players", label: `${Term("team", 2)} & ${term("player", 2)}` },
];

export function SetupSteps({ current }: { current: SetupStep }) {
  return (
    <ol className="setup-steps">
      {STEPS.map((s, i) => (
        <li key={s.step} className={s.step === current ? "active" : ""} aria-current={s.step === current ? "step" : undefined}>
          <span className="step-number">{i + 1}</span> {s.label}
        </li>
      ))}
    </ol>
  );
}
