export function ErrorBanner({ message }: { message: string | null }) {
  return message ? <p className="error">{message}</p> : null;
}

export function Loading() {
  return <p className="muted">Loading…</p>;
}
