"use client";

import React from "react";

import { endpoints, getRole, setRole as persistRole } from "@/lib/api";
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

/**
 * What the active role is permitted to do.
 *
 * The table comes from `/api/roles`, which publishes the same map the routes
 * enforce, so a disabled control and a server refusal always agree. It is
 * fetched once per page load and cached at module scope: the table is static
 * for a build, and re-requesting it on every component that needs it would put
 * a round trip in front of a button.
 *
 * Before the table arrives, `can` returns true. A control that flickers from
 * enabled to disabled is a smaller problem than one that appears broken for a
 * moment, and the server is the thing actually enforcing this — an optimistic
 * click during that window is refused with the reason, not silently accepted.
 */
export type Capabilities = {
  ready: boolean;
  can: (capability: string) => boolean;
  why: (capability: string) => string;
};

let capabilityCache: Record<string, { capabilities: string[]; denied: Record<string, string> }> | null =
  null;
let capabilityInFlight: Promise<void> | null = null;

export function useCapabilities(): Capabilities {
  const [role] = useRole();
  const [table, setTable] = React.useState(capabilityCache);

  React.useEffect(() => {
    if (capabilityCache) {
      setTable(capabilityCache);
      return;
    }
    let cancelled = false;
    const pending =
      capabilityInFlight ||
      endpoints
        .roles()
        .then((res: any) => {
          capabilityCache = res?.capabilities ?? null;
        })
        .catch(() => {
          // Leave the cache empty; `can` stays permissive and the server refuses.
          capabilityCache = null;
        })
        .finally(() => {
          capabilityInFlight = null;
        });
    capabilityInFlight = pending;
    pending.then(() => {
      if (!cancelled) setTable(capabilityCache);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const entry = table?.[role];
  return {
    ready: Boolean(entry),
    can: (capability: string) =>
      entry ? entry.capabilities.includes(capability) : true,
    why: (capability: string) => entry?.denied?.[capability] ?? "",
  };
}
