// Mirrors app/schemas.py and app/routers/api.py's response models. Field
// casing matches the wire exactly -- FastAPI serializes Pydantic's `alias`
// (populate_by_name=True) fields as camelCase, confirmed empirically against
// a running instance, not assumed from the Python names.

export interface HouseholdMember {
  name: string;
  // Free-text notes (e.g. "vegetarian", "doesn't like spicy food") fed into
  // the Gemini chat agent's system instructions.
  preferences: string | null;
}

export interface Household {
  id: number;
  name: string;
  members: HouseholdMember[];
  // True only when a token exists AND isn't expired.
  connected: boolean;
  // True only when a token exists but is expired -- distinguishes "never
  // connected" from "was connected, needs reconnecting" for UI copy.
  tokenExpired: boolean;
}

// -- Dineout --

export interface DineoutRating {
  value: string | null;
  count: number | null;
}

export interface DineoutOffer {
  offerTitle: string;
  offerDescription: string | null;
}

export interface DineoutRestaurant {
  id: string;
  name: string;
  cuisine: string[];
  locality: string | null;
  area: string | null;
  rating: DineoutRating | null;
  costForTwo: string | null;
  imageUrl: string | null;
  distance: string | null;
  highlights: string[];
  offers: DineoutOffer[];
}

export interface DineoutSearchResult {
  restaurants: DineoutRestaurant[];
  latitude: number | null;
  longitude: number | null;
  total: number;
  offset: number;
  nextOffset: number | null;
}

// -- Instamart --

export interface InstamartAddress {
  id: string;
  addressLine: string | null;
  phoneNumber: string | null;
  addressCategory: string | null;
  addressTag: string | null;
}

export interface InstamartPrice {
  mrp: number | null;
  offerPrice: number | null;
  unitLevelPrice: string | null;
}

export interface InstamartVariation {
  spinId: string | null;
  skuId: string | null;
  quantityDescription: string | null;
  price: InstamartPrice | null;
  isInStockAndAvailable: boolean | null;
}

export interface InstamartProduct {
  productId: string;
  displayName: string;
  brand: string | null;
  inStock: boolean;
  isAvail: boolean | null;
  isPromoted: boolean;
  variations: InstamartVariation[];
}

export interface InstamartSearchResult {
  products: InstamartProduct[];
  similarProducts: InstamartProduct[];
  nextOffset: string | null;
}

export interface InstamartCartLineItem {
  label: string | null;
  value: string | null;
}

export interface InstamartCartBillBreakdown {
  lineItems: InstamartCartLineItem[];
  toPay: InstamartCartLineItem | null;
}

export interface InstamartCartItem {
  spinId: string;
  skuId: string | null;
  productId: string | null;
  itemName: string;
  itemVariant: string | null;
  quantity: number;
  isInStockAndAvailable: boolean | null;
  mrp: number | null;
  discountedFinalPrice: number | null;
  imageUrl: string | null;
  maxQuantity: number | null;
  maxQuantityMessage: string | null;
}

export interface InstamartCart {
  cartTotalAmount: string | null;
  items: InstamartCartItem[];
  billBreakdown: InstamartCartBillBreakdown | null;
  cartAbsent: boolean;
  cartId: string | null;
}

// -- Chat --

export interface ChatTurnResult {
  transcript: { role: "user" | "assistant"; text: string }[];
  // Opaque Gemini turn history -- round-tripped, never read by the frontend.
  history: Record<string, unknown>[];
}
