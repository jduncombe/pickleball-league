"use client";

import { useCallback, useEffect, useState } from "react";

/** Load data on mount (and whenever `deps` change); exposes `reload` for after mutations. */
export function useLoader<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);

  const reload = useCallback(async () => {
    try {
      setData(await run());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    setLoading(true);
    reload();
  }, [reload]);

  return { data, error, loading, reload };
}
