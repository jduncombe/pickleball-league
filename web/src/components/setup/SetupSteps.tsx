import type { SetupStep } from "@/lib/routes";

const STEPS: { step: SetupStep; label: string }[] = [
  { step: "basics", label: "League basics" },
  { step: "players", label: "Teams & players" },
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
