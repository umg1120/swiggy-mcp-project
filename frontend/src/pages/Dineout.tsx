import { useState } from "react";
import { api, ApiError } from "../api";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardFooter, CardMedia, CardText, CardTitle } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHead } from "../components/Chai";
import { ErrorBanner } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";
import type { DineoutSearchResult } from "../types";

export default function Dineout() {
  const { error: householdsError, selected } = useHousehold();
  const householdId = selected?.connected ? selected.id : null;
  const [query, setQuery] = useState("");
  const [latitude, setLatitude] = useState("12.9351"); // Koramangala, Bengaluru -- a sane default
  const [longitude, setLongitude] = useState("77.6146");
  const [placeLabel, setPlaceLabel] = useState("Koramangala, Bengaluru");
  const [editingPlace, setEditingPlace] = useState(false);
  const [locating, setLocating] = useState(false);
  const [results, setResults] = useState<DineoutSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function locateMe() {
    if (!navigator.geolocation) {
      setError("This browser can't share its location. Enter coordinates instead.");
      setEditingPlace(true);
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude.toFixed(4));
        setLongitude(pos.coords.longitude.toFixed(4));
        setPlaceLabel("you");
        setEditingPlace(false);
        setLocating(false);
      },
      () => {
        setError("Location access was blocked. Allow it in the browser, or enter coordinates instead.");
        setEditingPlace(true);
        setLocating(false);
      },
      { timeout: 10000 },
    );
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (householdId === null) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.dineoutSearch({
        householdId,
        query,
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
      });
      setResults(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHead title="Dineout">
        Restaurants near <span className="highlight">{placeLabel}</span>, with ratings, offers and cost for two.
      </PageHead>

      {householdsError && <ErrorBanner message={householdsError} />}

      {householdId !== null && (
        <form onSubmit={onSearch} className="flex flex-col gap-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <Field label="What are you craving?" className="md:flex-1">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Biryani, pizza, South Indian…" required />
            </Field>
            <Button type="submit" variant="solid" disabled={loading} className="self-start md:self-auto">
              {loading ? "Searching…" : "Search"}
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="text-muted-foreground">
              Near <span className="text-foreground">{placeLabel}</span>
            </span>
            <Button type="button" variant="ghost" size="sm" onClick={locateMe} disabled={locating}>
              {locating ? "Finding you…" : "Use my location"}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditingPlace((v) => !v)} aria-expanded={editingPlace}>
              {editingPlace ? "Done" : "Enter coordinates"}
            </Button>
          </div>

          {editingPlace && (
            <div className="grid grid-cols-2 gap-3 sm:max-w-md">
              <Field label="Latitude">
                <Input
                  value={latitude}
                  onChange={(e) => {
                    setLatitude(e.target.value);
                    setPlaceLabel("those coordinates");
                  }}
                  inputMode="decimal"
                  required
                />
              </Field>
              <Field label="Longitude">
                <Input
                  value={longitude}
                  onChange={(e) => {
                    setLongitude(e.target.value);
                    setPlaceLabel("those coordinates");
                  }}
                  inputMode="decimal"
                  required
                />
              </Field>
            </div>
          )}
        </form>
      )}

      {error && <ErrorBanner message={error} />}

      {results && (
        <section aria-label="Restaurants" className="flex flex-col gap-4">
          <p className="muted">
            {results.restaurants.length === 0
              ? "No restaurants matched. Try another dish or a wider area."
              : `${results.restaurants.length} restaurant${results.restaurants.length === 1 ? "" : "s"} found`}
          </p>
          {results.restaurants.length > 0 && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
              {results.restaurants.map((r) => (
                <Card key={r.id}>
                  {r.imageUrl?.startsWith("http") && (
                    <CardMedia>
                      <img src={r.imageUrl} alt="" loading="lazy" />
                    </CardMedia>
                  )}
                  <CardBody>
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle>{r.name}</CardTitle>
                      {r.rating?.value && (
                        <Chip tone="success" className="shrink-0" aria-label={`Rated ${r.rating.value}`}>
                          ★ {r.rating.value}
                        </Chip>
                      )}
                    </div>
                    {r.cuisine.length > 0 && <CardText>{r.cuisine.join(", ")}</CardText>}
                    {(r.locality || r.distance) && (
                      <CardText>
                        {r.locality}
                        {r.locality && r.distance ? ", " : ""}
                        {r.distance && `${r.distance} away`}
                      </CardText>
                    )}
                    {r.offers.length > 0 && (
                      <ul className="flex flex-wrap gap-1.5 pt-1">
                        {r.offers.map((o, i) => (
                          <li key={i}>
                            <Chip tone="success">{o.offerTitle}</Chip>
                          </li>
                        ))}
                      </ul>
                    )}
                    {r.costForTwo && (
                      <CardFooter>
                        <p className="font-montserrat text-sm font-semibold">₹{r.costForTwo} for two</p>
                      </CardFooter>
                    )}
                  </CardBody>
                </Card>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
