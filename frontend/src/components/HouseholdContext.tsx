import { createContext, use, type ReactNode } from "react";
import { useHouseholds, useSelectedHousehold } from "../hooks";
import type { Household } from "../types";

type HouseholdState = {
  households: Household[] | null;
  error: string | null;
  reload: () => void;
  selectedId: number | null;
  setSelectedId: (id: number) => void;
  selected: Household | null;
};

const HouseholdContext = createContext<HouseholdState | null>(null);

/** One household list + selection for the whole app, so the household strip
 * under the navbar and every page agree on the same household (previously
 * each page loaded and picked its own). */
export function HouseholdProvider({ children }: { children: ReactNode }) {
  const { households, error, reload } = useHouseholds();
  const [selectedId, setSelectedId] = useSelectedHousehold(households);
  const selected = households?.find((h) => h.id === selectedId) ?? null;
  return (
    <HouseholdContext value={{ households, error, reload, selectedId, setSelectedId, selected }}>
      {children}
    </HouseholdContext>
  );
}

export function useHousehold() {
  const ctx = use(HouseholdContext);
  if (!ctx) throw new Error("useHousehold must be used inside <HouseholdProvider>");
  return ctx;
}
