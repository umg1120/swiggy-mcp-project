// Thin fetch wrapper for app/routers/api.py. Every call is same-origin in
// dev (Vite proxies /api -> http://localhost:8000, see vite.config.ts), so
// there's no base URL to configure.

import type {
  ChatTurnResult,
  DineoutSearchResult,
  Household,
  HouseholdMember,
  InstamartAddress,
  InstamartCart,
  InstamartSearchResult,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// Set by AuthGate (App.tsx) so any 401 -- from any call, anywhere -- flips
// the whole app back to the login screen, instead of every page having to
// notice and handle it individually.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (res.status === 401) {
    onUnauthorized?.();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body -- fall back to statusText
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) usp.set(k, String(v));
  }
  return usp.toString();
}

export const api = {
  listHouseholds: () => request<Household[]>("/api/households"),
  createHousehold: (name: string, members: Pick<HouseholdMember, "name" | "preferences">[]) =>
    request<Household>("/api/households", {
      method: "POST",
      body: JSON.stringify({
        name,
        members: members.map((m) => ({ name: m.name, preferences: m.preferences || null })),
      }),
    }),
  updateHousehold: (
    id: number,
    name: string,
    members: Pick<HouseholdMember, "name" | "preferences">[],
  ) =>
    request<Household>(`/api/households/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        name,
        members: members.map((m) => ({ name: m.name, preferences: m.preferences || null })),
      }),
    }),
  disconnectHousehold: (id: number) =>
    request<Household>(`/api/households/${id}/connection`, { method: "DELETE" }),

  dineoutSearch: (args: {
    householdId: number;
    query: string;
    latitude: number;
    longitude: number;
  }) =>
    request<DineoutSearchResult>(
      `/api/dineout/search?${qs({
        household_id: args.householdId,
        query: args.query,
        latitude: args.latitude,
        longitude: args.longitude,
      })}`,
    ),

  instamartAddresses: (householdId: number) =>
    request<InstamartAddress[]>(`/api/instamart/addresses?${qs({ household_id: householdId })}`),

  instamartSearch: (args: { householdId: number; addressId: string; query: string }) =>
    request<InstamartSearchResult>(
      `/api/instamart/search?${qs({
        household_id: args.householdId,
        address_id: args.addressId,
        query: args.query,
      })}`,
    ),

  instamartCart: (householdId: number) =>
    request<InstamartCart>(`/api/instamart/cart?${qs({ household_id: householdId })}`),

  instamartCartAdd: (args: {
    householdId: number;
    addressId: string;
    spinId: string;
    skuId?: string | null;
    quantity?: number;
  }) =>
    request<InstamartCart>("/api/instamart/cart/add", {
      method: "POST",
      body: JSON.stringify({
        household_id: args.householdId,
        address_id: args.addressId,
        spin_id: args.spinId,
        sku_id: args.skuId ?? null,
        quantity: args.quantity ?? 1,
      }),
    }),

  instamartCartClear: (householdId: number) =>
    request<InstamartCart>("/api/instamart/cart/clear", {
      method: "POST",
      body: JSON.stringify({ household_id: householdId }),
    }),

  chatTurn: (args: {
    householdId: number;
    addressId?: string | null;
    message: string;
    history: Record<string, unknown>[];
  }) =>
    request<ChatTurnResult>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        household_id: args.householdId,
        address_id: args.addressId ?? null,
        message: args.message,
        history: args.history,
      }),
    }),

  // App-level login (a person using this app at all) -- distinct from
  // /connect's Swiggy OAuth (a household's own Swiggy account).
  login: (password: string) =>
    request<{ authenticated: boolean }>("/auth/session/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => request<{ authenticated: boolean }>("/auth/session/logout", { method: "POST" }),
  me: () => request<{ authenticated: boolean }>("/auth/session/me"),
};
