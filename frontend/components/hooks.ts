"use client";

import React from "react";

import { getRole, setRole as persistRole } from "@/lib/api";
import type { Role } from "@/lib/domain";

/** Minimal data-fetching hook: loading, error, data, refetch. No client cache library. */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = [],
  options: { enabled?: boolean } = {},
) {
  const enabled = options.enabled !== false;
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(enabled);
  const [nonce, setNonce] = React.useState(0);
  const fetcherRef = React.useRef(fetcher);
  fetcherRef.current = fetcher;

  React.useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  const refetch = React.useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, refetch, setData };
}

/**
 * The active demo role, shared across the app.
 *
 * Role lives in localStorage so it survives a refresh mid-demonstration, and a
 * custom event keeps every mounted component in step when it changes.
 */
export function useRole(): [Role, (role: Role) => void] {
  const [role, setRoleState] = React.useState<Role>("BUYER");

  React.useEffect(() => {
    setRoleState(getRole());
    const onChange = (e: Event) => setRoleState((e as CustomEvent).detail as Role);
    window.addEventListener("ltc:role", onChange);
    return () => window.removeEventListener("ltc:role", onChange);
  }, []);

  const update = React.useCallback((next: Role) => {
    persistRole(next);
    setRoleState(next);
  }, []);

  return [role, update];
}

/** Reads/writes a single query-string key without a full navigation. */
export function useQueryParam(key: string, fallback: string): [string, (v: string) => void] {
  const [value, setValue] = React.useState(fallback);

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setValue(params.get(key) || fallback);
  }, [key, fallback]);

  const update = React.useCallback(
    (next: string) => {
      setValue(next);
      const params = new URLSearchParams(window.location.search);
      params.set(key, next);
      window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
    },
    [key],
  );

  return [value, update];
}

export function useMounted() {
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  return mounted;
}
