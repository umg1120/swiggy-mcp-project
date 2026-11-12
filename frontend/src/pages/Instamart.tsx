import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { PageHead } from "../components/Chai";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";
import type { InstamartAddress, InstamartCart, InstamartSearchResult } from "../types";

export default function Instamart() {
  const { error: householdsError, selected } = useHousehold();
  // Only act for a household that's actually connected to Swiggy; the strip
  // above the page links to /connect for the rest.
  const householdId = selected?.connected ? selected.id : null;
  const [addresses, setAddresses] = useState<InstamartAddress[] | null>(null);
  const [addressId, setAddressId] = useState<string>("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstamartSearchResult | null>(null);
  const [cart, setCart] = useState<InstamartCart | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (householdId === null) return;
    setAddresses(null);
    setResults(null);
    setError(null);
    api
      .instamartAddresses(householdId)
      .then((addrs) => {
        setAddresses(addrs);
        if (addrs.length > 0) setAddressId(addrs[0].id);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load addresses"));
    api.instamartCart(householdId).then(setCart).catch(() => {});
  }, [householdId]);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (householdId === null || !addressId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.instamartSearch({ householdId, addressId, query });
      setResults(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function addToCart(spinId: string, skuId: string | null, name: string) {
    if (householdId === null || !addressId) return;
    setAddingId(spinId);
    setError(null);
    try {
      const updated = await api.instamartCartAdd({ householdId, addressId, spinId, skuId, quantity: 1 });
      setCart(updated);
      toast(`Added ${name} to cart`, { tone: "success" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add to cart");
    } finally {
      setAddingId(null);
    }
  }

  async function clearCart() {
    if (householdId === null) return;
    setClearing(true);
    setClearError(null);
    try {
      setCart(await api.instamartCartClear(householdId));
      setConfirmClear(false);
      toast("Cart cleared", { tone: "success" });
    } catch (err) {
      // Shown inside the dialog, so the person can retry or cancel.
      setClearError(err instanceof ApiError ? err.message : "Could not clear cart");
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHead title="Instamart">
        Search groceries and add them to <span className="highlight">{selected?.name ?? "the household"}</span>'s
        Instamart cart.
      </PageHead>

      {householdsError && <ErrorBanner message={householdsError} />}

      {householdId !== null && (
        <>
          {addresses === null ? (
            <Spinner label="Loading delivery addresses" />
          ) : addresses.length === 0 ? (
            <p className="muted">
              This Swiggy account has no saved delivery address. Add one in the Swiggy app, then reload.
            </p>
          ) : (
            <form onSubmit={onSearch} className="flex flex-col gap-3 md:flex-row md:items-end">
              <Field label="Search groceries" className="md:flex-1">
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Milk, atta, chips…" required />
              </Field>
              <Field label="Deliver to" className="md:w-80">
                <Select wrapperClassName="w-full" className="w-full" value={addressId} onChange={(e) => setAddressId(e.target.value)}>
                  {addresses.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.addressLine ?? a.id}
                    </option>
                  ))}
                </Select>
              </Field>
              <Button type="submit" variant="solid" disabled={loading} className="self-start md:self-auto">
                {loading ? "Searching…" : "Search"}
              </Button>
            </form>
          )}
        </>
      )}

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_20rem] lg:items-start">
        <section aria-label="Search results" className="min-w-0">
          {results === null ? (
            <p className="muted">Search for something to see what's in stock near the delivery address.</p>
          ) : results.products.length === 0 ? (
            <p className="muted">Nothing found. Try a shorter or more general word.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {results.products.map((p) => {
                const v = p.variations[0];
                const discounted =
                  v?.price?.mrp != null && v.price.offerPrice != null && v.price.mrp !== v.price.offerPrice;
                return (
                  <li key={p.productId} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0">
                    <div className="min-w-0">
                      <p className="font-montserrat leading-snug font-semibold">{p.displayName}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.brand}
                        {v?.quantityDescription && `, ${v.quantityDescription}`}
                      </p>
                      {v?.price && (
                        <p className="mt-1 font-montserrat text-sm">
                          <span className="font-semibold">₹{v.price.offerPrice ?? v.price.mrp}</span>
                          {discounted && (
                            <span className="ml-1.5 text-xs text-red-600/80 line-through dark:text-red-400/80">
                              ₹{v.price.mrp}
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                    {v?.spinId && v.isInStockAndAvailable ? (
                      <Button
                        size="sm"
                        className="min-w-24"
                        onClick={() => addToCart(v.spinId!, v.skuId, p.displayName)}
                        disabled={addingId === v.spinId}
                      >
                        {addingId === v.spinId ? "Adding…" : "Add to cart"}
                      </Button>
                    ) : (
                      <span className="text-xs text-red-600 dark:text-red-400">Out of stock</span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* The cart is the one framed panel on the page, pinned while scrolling results. */}
        <GlassPanel className="lg:sticky lg:top-24">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-montserrat text-lg font-semibold">Cart</h2>
            {cart && !cart.cartAbsent && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setClearError(null);
                  setConfirmClear(true);
                }}
              >
                Clear cart
              </Button>
            )}
          </div>
          {!cart || cart.cartAbsent ? (
            <p className="muted">The cart is empty. Items you add appear here.</p>
          ) : (
            <div className="flex flex-col gap-2">
              <ul className="flex flex-col gap-2 text-sm">
                {cart.items.map((it) => (
                  <li key={it.spinId} className="flex justify-between gap-3">
                    <span className="min-w-0">
                      {it.itemName} <span className="text-muted-foreground">× {it.quantity}</span>
                    </span>
                    <span className="shrink-0 font-montserrat font-medium">₹{it.discountedFinalPrice ?? it.mrp}</span>
                  </li>
                ))}
              </ul>
              {cart.billBreakdown?.toPay && (
                <div className="mt-2 flex justify-between border-t border-border pt-3 font-montserrat font-semibold">
                  <span>{cart.billBreakdown.toPay.label ?? "To pay"}</span>
                  <span>{cart.billBreakdown.toPay.value}</span>
                </div>
              )}
            </div>
          )}
        </GlassPanel>
      </div>

      <ConfirmDialog
        open={confirmClear}
        title="Clear the Instamart cart?"
        confirmLabel="Clear cart"
        busyLabel="Clearing…"
        cancelLabel="Keep the cart"
        busy={clearing}
        error={clearError}
        onConfirm={clearCart}
        onCancel={() => setConfirmClear(false)}
      >
        <p>
          This removes all {cart && !cart.cartAbsent ? cart.items.length : ""} items from {selected?.name ?? "this household"}'s
          Swiggy Instamart cart, including anything added from the Swiggy app.
        </p>
      </ConfirmDialog>
    </div>
  );
}
