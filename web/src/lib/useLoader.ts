"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Loaded<T> = { key: string; data: T | null; error: string | null };

/** Load data on mount (and whenever `deps` change); exposes `reload` for after mutations. */
export function useLoader<T>(load: () => Promise<T>, deps: unknown[] = []) {
  // `deps` are ids and counts, so their JSON is a stable key for them.
  const key = JSON.stringify(deps);
  const [state, setState] = useState<Loaded<T> | null>(null);

  // The latest `load`, which closes over the latest props.
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  });

  const reload = useCallback(async () => {
    try {
      const data = await loadRef.current();
      setState({ key, data, error: null });
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      setState((prev) => ({ key, data: prev?.data ?? null, error }));
    }
  }, [key]);

  useEffect(() => {
    reload();
  }, [reload]);

  // While `deps` change, the previous data stays visible with `loading` true.
  return {
    data: state?.data ?? null,
    error: state?.error ?? null,
    loading: state?.key !== key,
    reload,
  };
}
