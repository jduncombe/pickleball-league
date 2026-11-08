"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ErrorBanner, Loading } from "@/components/Status";
import { ApiError, api } from "@/lib/api";
import { safeNext, useAuth } from "@/lib/auth";
import type { MfaSetup } from "@/lib/types";

type Step =
  | { kind: "password" }
  | { kind: "setup"; mfaToken: string; setup: MfaSetup }
  | { kind: "code"; mfaToken: string };

/** Sign in: email and password, then a code from an authenticator app (set up at first sign-in). */
export default function LoginPage() {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense fallback={<Loading />}>
      <Login />
    </Suspense>
  );
}

function Login() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const { refresh } = useAuth();
  const [step, setStep] = useState<Step>({ kind: "password" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      // The MFA step token lasts 5 minutes; after that, start again.
      if (err instanceof ApiError && err.status === 401 && /expired|invalid/i.test(err.message)) {
        setStep({ kind: "password" });
      }
    } finally {
      setBusy(false);
    }
  }

  const submitPassword = (form: FormData) =>
    run(async () => {
      const result = await api.login(String(form.get("email")), String(form.get("password")));
      if (result.mfa_setup_required) {
        const setup = await api.mfaSetup(result.mfa_token);
        setStep({ kind: "setup", mfaToken: result.mfa_token, setup });
      } else {
        setStep({ kind: "code", mfaToken: result.mfa_token });
      }
    });

  const submitCode = (mfaToken: string, form: FormData) =>
    run(async () => {
      await api.mfaVerify(mfaToken, String(form.get("code")));
      await refresh();
      router.replace(next);
    });

  return (
    <div className="login">
      <div className="card">
        <h1>Sign in</h1>
        <ErrorBanner message={error} />

        {step.kind === "password" && (
          <form className="stack" onSubmit={formHandler(submitPassword)}>
            <label className="field">
              <span>Email</span>
              <input name="email" type="email" autoComplete="username" required autoFocus />
            </label>
            <label className="field">
              <span>Password</span>
              <input name="password" type="password" autoComplete="current-password" required />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Checking…" : "Continue"}
            </button>
          </form>
        )}

        {step.kind === "setup" && (
          <div className="stack">
            <p>
              Your account needs two-step sign-in. Scan this code with an authenticator app (such as Google
              Authenticator, Microsoft Authenticator or 1Password), then enter the 6-digit code it shows.
            </p>
            {/* An <img>, not inline SVG, so the markup can't run anything. */}
            {step.setup.qr_data_uri.startsWith("data:image/svg+xml") && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="qr"
                src={step.setup.qr_data_uri}
                alt="QR code for your authenticator app"
                width={200}
                height={200}
              />
            )}
            <details>
              <summary>Can&apos;t scan it?</summary>
              <p className="muted">Enter this key in the app instead (time-based, 6 digits):</p>
              <code className="secret">{step.setup.secret.match(/.{1,4}/g)?.join(" ")}</code>
            </details>
            <CodeForm busy={busy} onSubmit={(form) => submitCode(step.mfaToken, form)} />
          </div>
        )}

        {step.kind === "code" && (
          <div className="stack">
            <p>Enter the 6-digit code from your authenticator app.</p>
            <CodeForm busy={busy} onSubmit={(form) => submitCode(step.mfaToken, form)} />
            <p className="muted small">Lost your authenticator? Ask an admin to reset it.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/** Submit without the page reload, and without React resetting the fields on error. */
function formHandler(handle: (form: FormData) => void) {
  return (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    handle(new FormData(event.currentTarget));
  };
}

function CodeForm({ busy, onSubmit }: { busy: boolean; onSubmit: (form: FormData) => void }) {
  return (
    <form className="stack" onSubmit={formHandler(onSubmit)}>
      <label className="field">
        <span>Code</span>
        <input
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9 ]{6,7}"
          maxLength={7}
          required
          autoFocus
        />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? "Checking…" : "Sign in"}
      </button>
    </form>
  );
}
