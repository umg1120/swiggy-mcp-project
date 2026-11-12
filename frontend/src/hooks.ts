import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Household } from "./types";

/** Shared across every page that needs a household list + connect status. */
export function useHouseholds() {
  const [households, setHouseholds] = useState<Household[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    api
      .listHouseholds()
      .then(setHouseholds)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(reload, [reload]);

  return { households, error, reload };
}

const SELECTED_HOUSEHOLD_KEY = "swiggy-mcp:selectedHouseholdId";

function readPersistedHouseholdId(): number | null {
  try {
    const raw = localStorage.getItem(SELECTED_HOUSEHOLD_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null; // e.g. private-browsing mode blocking storage access
  }
}

/** The active household, shared and persisted across every page (Home,
 * Dineout, Instamart, Chat) instead of each page re-picking it from
 * scratch. Falls back to a connected household once the list loads, if
 * nothing (valid) was persisted -- and re-falls-back if the persisted
 * household is still there but its Swiggy connection has since expired,
 * rather than silently keep using it and hitting an expired-token error
 * on every request with no visible reason why (a real bug hit live: a
 * household selected while connected, whose token later expired, kept
 * being used -- the household picker wouldn't even show it as selectable
 * anymore, but this hook kept it active regardless). */
export function useSelectedHousehold(
  households: Household[] | null,
): [number | null, (id: number) => void] {
  const [selectedId, setSelectedIdState] = useState<number | null>(readPersistedHouseholdId);

  const setSelectedId = useCallback((id: number) => {
    setSelectedIdState(id);
    try {
      localStorage.setItem(SELECTED_HOUSEHOLD_KEY, String(id));
    } catch {
      // ignore -- selection still works for this session, just won't persist
    }
  }, []);

  useEffect(() => {
    if (!households) return;
    const selected = households.find((h) => h.id === selectedId);
    if (selected?.connected) return; // still a valid, connected selection
    const fallback = households.find((h) => h.connected) ?? households[0];
    if (fallback && fallback.id !== selectedId) setSelectedId(fallback.id);
  }, [households, selectedId, setSelectedId]);

  return [selectedId, setSelectedId];
}
