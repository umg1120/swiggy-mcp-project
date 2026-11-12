import { ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardText, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "../api";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";
import type { Household, InstamartCart } from "../types";

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** Starter asks written from the household's own members and preferences --
 * the thing that makes this agent different from a plain search box. */
function suggestionsFor(household: Household | null): string[] {
  const withPrefs = household?.members.filter((m) => m.preferences) ?? [];
  const dinner =
    withPrefs.length > 0
      ? `Find a dinner spot nearby for ${joinNames(withPrefs.map((m) => m.name))}: ${withPrefs
          .map((m) => m.preferences)
          .join(", ")}`
      : "Find a well-rated biryani place nearby";
  return [dinner, "Add milk, eggs and bread to the cart", "What's in our Instamart cart?"];
}

export default function Home() {
  const { households, error: householdsError, selected } = useHousehold();
  const [cart, setCart] = useState<InstamartCart | null>(null);
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (!selected?.connected) {
      setCart(null);
      return;
    }
    api.instamartCart(selected.id).then(setCart).catch(() => setCart(null));
  }, [selected?.id, selected?.connected]);

  function ask(text: string) {
    if (!text.trim()) return;
    // Hand off as a draft rather than auto-sending -- Chat still needs to
    // load this household's addresses before a real turn can go out.
    navigate("/chat", { state: { draft: text.trim() } });
  }

  const cartLine =
    cart && !cart.cartAbsent
      ? `${cart.items.length} item${cart.items.length === 1 ? "" : "s"}${
          cart.billBreakdown?.toPay?.value ? `, ${cart.billBreakdown.toPay.value} to pay` : ""
        }`
      : null;

  return (
    <div className="flex flex-col gap-12">
      {/* Hero: one central element, the ask bar, with asks written from this
          household's preferences. Enters once, in sequence (.hero-enter). */}
      <section className="hero-enter flex flex-col items-center gap-5 pt-6 text-center sm:pt-12">
        <h1 className="max-w-4xl text-[42px] text-balance leading-11 font-semibold tracking-tight md:text-6xl md:leading-none lg:text-7xl">
          What are you in the mood for?
        </h1>
        <p className="max-w-2xl text-base text-neutral-700 md:text-xl dark:text-neutral-400">
          Ask once and the agent searches Instamart and Dineout for{" "}
          <span className="highlight">{selected ? selected.name : "your household"}</span>, with everyone's
          preferences in mind.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(message);
          }}
          className="mt-3 flex w-full max-w-2xl flex-col gap-3 sm:flex-row"
        >
          <Input
            className="h-12 px-4 text-base sm:flex-1"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask for food or groceries"
            aria-label="Ask the agent"
          />
          <Button type="submit" variant="solid" size="lg" disabled={!message.trim()} className="h-12">
            Ask
          </Button>
        </form>
        {selected?.connected && (
          <ul className="flex max-w-2xl flex-wrap justify-center gap-2" aria-label="Suggested asks">
            {suggestionsFor(selected).map((s) => (
              <li key={s}>
                <Button variant="muted" size="sm" className="h-auto max-w-full py-1.5 text-center whitespace-normal" onClick={() => ask(s)}>
                  {s}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {householdsError && <ErrorBanner message={householdsError} />}

      {households !== null && households.length === 0 && (
        <GlassPanel>
          <h2 className="section-title">Set up your household</h2>
          <p className="muted mt-1">
            Add the people you order for and what they like. Dineout, Instamart and Chat all work for one
            household at a time.
          </p>
          <Button asChild className="mt-4">
            <Link to="/households">Create a household</Link>
          </Button>
        </GlassPanel>
      )}

      {selected && !selected.connected && (
        <GlassPanel>
          <h2 className="section-title">
            {selected.tokenExpired ? "Reconnect" : "Connect"} {selected.name} to Swiggy
          </h2>
          <p className="muted mt-1">
            {selected.tokenExpired
              ? "This household's Swiggy sign-in has expired. Reconnect it to search and order again."
              : "Sign in to the household's Swiggy account so the agent can search and order for it."}
          </p>
          <Button asChild className="mt-4">
            <Link to="/connect">{selected.tokenExpired ? "Reconnect Swiggy" : "Connect Swiggy"}</Link>
          </Button>
        </GlassPanel>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <ServiceCard to="/instamart" title="Instamart" note={cartLine}>
          Search groceries and add them to the household's Instamart cart yourself.
        </ServiceCard>
        <ServiceCard to="/dineout" title="Dineout">
          Browse restaurants near any location, with ratings, offers and cost for two.
        </ServiceCard>
      </div>
    </div>
  );
}

function ServiceCard({
  to,
  title,
  note,
  children,
}: {
  to: string;
  title: string;
  note?: string | null;
  children: React.ReactNode;
}) {
  return (
    <Link to={to} className="rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
      <Card className="h-full">
        <CardBody className="p-5 sm:p-6">
          <CardTitle className="flex items-center gap-1.5 text-lg">
            {title}
            <ArrowUpRight className="size-4" aria-hidden="true" />
          </CardTitle>
          <CardText className="text-sm">{children}</CardText>
          {note && <p className="mt-2 font-montserrat text-sm font-medium text-highlight">In the cart: {note}</p>}
        </CardBody>
      </Card>
    </Link>
  );
}
