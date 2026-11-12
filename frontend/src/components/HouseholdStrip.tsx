import { Link } from "react-router-dom";
import { Chip } from "@/components/ui/chip";
import { Segmented } from "@/components/ui/segmented";
import { useHousehold } from "./HouseholdContext";

/** The household strip under the navbar on Home/Dineout/Instamart/Chat: which
 * household everything acts for, plus its members' preferences (what the Chat
 * agent is told about them). Replaces the "1. Pick a household" card each of
 * those pages used to repeat. */
export function HouseholdStrip() {
  const { households, selected, selectedId, setSelectedId } = useHousehold();
  if (!households) return null;

  if (households.length === 0) {
    return (
      <p className="muted">
        No households yet.{" "}
        <Link to="/households" className="link text-foreground">
          Create one first
        </Link>
        .
      </p>
    );
  }

  const connected = households.filter((h) => h.connected);
  const disconnected = households.filter((h) => !h.connected);
  const preferences = selected?.connected ? selected.members.filter((m) => m.preferences) : [];

  return (
    <div className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        {connected.length > 0 && (
          <Segmented
            label="Household"
            className="w-fit"
            options={connected.map((h) => ({ value: String(h.id), label: h.name }))}
            value={selectedId === null ? "" : String(selectedId)}
            onChange={(v) => setSelectedId(Number(v))}
          />
        )}
        {preferences.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label={`${selected!.name} preferences`}>
            {preferences.map((m) => (
              <li key={m.name}>
                <Chip>
                  <span className="text-foreground">{m.name}</span> {m.preferences}
                </Chip>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {disconnected.map((h) => (
          <Link key={h.id} to="/connect" className="link">
            {h.tokenExpired ? `Reconnect ${h.name}` : `Connect ${h.name}`}
          </Link>
        ))}
        <Link to="/households" className="link">
          Edit households
        </Link>
      </p>
    </div>
  );
}
