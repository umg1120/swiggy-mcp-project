import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { PageHead } from "../components/Chai";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";
import type { ChatTurnResult, InstamartAddress } from "../types";

export default function Chat() {
  const { error: householdsError, selected } = useHousehold();
  const householdId = selected?.connected ? selected.id : null;
  const [addresses, setAddresses] = useState<InstamartAddress[] | null>(null);
  const [addressId, setAddressId] = useState<string>("");
  const [message, setMessage] = useState("");
  const [transcript, setTranscript] = useState<ChatTurnResult["transcript"]>([]);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();

  // Home's quick-ask bar hands off a draft message via router state instead
  // of auto-sending it -- addressId may not have loaded yet at this point,
  // so we just prefill and let the user hit Send once things are ready.
  useEffect(() => {
    const draft = (location.state as { draft?: string } | null)?.draft;
    if (draft) {
      setMessage(draft);
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  useEffect(() => {
    if (householdId === null) return;
    setAddresses(null);
    setTranscript([]);
    setHistory([]);
    setError(null);
    api
      .instamartAddresses(householdId)
      .then((addrs) => {
        setAddresses(addrs);
        if (addrs.length > 0) setAddressId(addrs[0].id);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load addresses"));
  }, [householdId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  async function onSend(e: React.FormEvent) {
    e.preventDefault();
    if (householdId === null || !message.trim()) return;
    const userText = message.trim();
    setMessage("");
    setSending(true);
    setError(null);
    // Optimistically show the user's turn -- the real transcript (which
    // includes it) replaces this once the reply lands.
    setTranscript((t) => [...t, { role: "user", text: userText }]);
    try {
      const result = await api.chatTurn({ householdId, addressId, message: userText, history });
      setTranscript(result.transcript);
      setHistory(result.history);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat call failed");
      setTranscript((t) => t.slice(0, -1)); // undo the optimistic bubble
      setMessage(userText); // let them retry without retyping
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHead title="Chat">
        Ask in plain words. The agent searches Dineout and Instamart and can{" "}
        <span className="highlight">fill the cart</span> for {selected?.name ?? "your household"}.
      </PageHead>

      {householdsError && <ErrorBanner message={householdsError} />}
      {error && <ErrorBanner message={error} />}

      {householdId !== null && (
        <GlassPanel className="flex flex-col gap-4">
          <div className="flex max-h-[55vh] min-h-[18rem] flex-col gap-3 overflow-y-auto pr-1" aria-live="polite">
            {transcript.length === 0 && !sending && (
              <p className="muted m-auto max-w-sm text-center">
                Ask for a restaurant, a grocery search, or a change to the cart. The agent already knows each
                member's preferences.
              </p>
            )}
            {transcript.map((turn, i) => (
              <div
                key={i}
                className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                  turn.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : "border border-card-edge text-foreground"
                }`}
              >
                {turn.text}
              </div>
            ))}
            {sending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner label="Agent is working" />
                Working on it…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={onSend} className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-end">
            <Field label="Message" className="sm:flex-1">
              <Input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Find a vegetarian thali place nearby"
                disabled={sending}
              />
            </Field>
            {addresses && addresses.length > 0 && (
              <Field label="Deliver to" className="sm:w-64">
                <Select wrapperClassName="w-full" className="w-full" value={addressId} onChange={(e) => setAddressId(e.target.value)}>
                  {addresses.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.addressLine ?? a.id}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Button type="submit" variant="solid" disabled={sending || !message.trim()} className="self-start sm:self-auto">
              {sending ? "Sending…" : "Send"}
            </Button>
          </form>
        </GlassPanel>
      )}
    </div>
  );
}
