import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, Fieldset } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { PageHead } from "../components/Chai";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";
import type { Household, HouseholdMember } from "../types";

type DraftMember = { name: string; preferences: string };

function emptyMember(): DraftMember {
  return { name: "", preferences: "" };
}

function toDraftMembers(members: HouseholdMember[]): DraftMember[] {
  return members.length > 0
    ? members.map((m) => ({ name: m.name, preferences: m.preferences ?? "" }))
    : [emptyMember()];
}

function cleanMembers(members: DraftMember[]): Pick<HouseholdMember, "name" | "preferences">[] {
  return members
    .filter((m) => m.name.trim())
    .map((m) => ({ name: m.name.trim(), preferences: m.preferences.trim() || null }));
}

/** Shared name+preferences row editor, reused by the create form and each
 * household's inline edit form. */
function MemberRowsEditor({
  members,
  onChange,
}: {
  members: DraftMember[];
  onChange: (members: DraftMember[]) => void;
}) {
  function update(i: number, patch: Partial<DraftMember>) {
    onChange(members.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  }

  return (
    <div className="flex flex-col gap-2">
      {members.map((m, i) => (
        <div key={i} className="flex flex-wrap gap-2">
          <Input
            className="flex-1 basis-32"
            aria-label={`Member ${i + 1} name`}
            value={m.name}
            onChange={(e) => update(i, { name: e.target.value })}
            placeholder="Name, e.g. Bob"
          />
          <Input
            className="flex-[2] basis-48"
            aria-label={`Member ${i + 1} preferences`}
            value={m.preferences}
            onChange={(e) => update(i, { preferences: e.target.value })}
            placeholder="Preferences, e.g. vegetarian, no spicy food"
          />
          <Button
            type="button"
            variant="ghost"
            onClick={() => onChange(members.filter((_, idx) => idx !== i))}
            aria-label={`Remove member ${i + 1}`}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="muted"
        size="sm"
        onClick={() => onChange([...members, emptyMember()])}
        className="self-start"
      >
        Add member
      </Button>
    </div>
  );
}

function EditHouseholdForm({
  household,
  onDone,
}: {
  household: Household;
  onDone: () => void;
}) {
  const [name, setName] = useState(household.name);
  const [members, setMembers] = useState<DraftMember[]>(() => toDraftMembers(household.members));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateHousehold(household.id, name.trim(), cleanMembers(members));
      toast(`Saved ${name.trim()}`, { tone: "success" });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save changes");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSave} className="flex flex-col gap-4 rounded-xl border border-card-edge p-4">
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </Field>
      <Fieldset legend="Members">
        <MemberRowsEditor members={members} onChange={setMembers} />
      </Fieldset>
      {error && <ErrorBanner message={error} />}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export default function Households() {
  const { households, error, reload } = useHousehold();
  const [name, setName] = useState("");
  const [members, setMembers] = useState<DraftMember[]>([emptyMember()]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const toast = useToast();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await api.createHousehold(name.trim(), cleanMembers(members));
      toast(`Created ${name.trim()}`, { tone: "success" });
      setName("");
      setMembers([emptyMember()]);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create household");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHead title="Households">
        Every Dineout, Instamart and Chat action is scoped to one of these. Member preferences feed
        straight into the <span className="highlight">Chat agent</span>.
      </PageHead>

      {error && <ErrorBanner message={error} />}

      <GlassPanel>
        <h2 className="section-title mb-4">Existing households</h2>
        {households === null ? (
          <Spinner label="Loading households" />
        ) : households.length === 0 ? (
          <p className="muted">None yet. Create one below.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {households.map((h) =>
              editingId === h.id ? (
                <li key={h.id} className="py-3 first:pt-0 last:pb-0">
                  <EditHouseholdForm household={h} onDone={() => {
                    setEditingId(null);
                    reload();
                  }} />
                </li>
              ) : (
                <li key={h.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{h.name}</span>
                    <div className="flex items-center gap-2">
                      {h.connected ? (
                        <Chip tone="success">Connected</Chip>
                      ) : h.tokenExpired ? (
                        <Chip className="border-yellow-600/30 text-yellow-700 dark:border-yellow-400/30 dark:text-yellow-400">
                          Reconnect needed
                        </Chip>
                      ) : (
                        <Chip>Not connected</Chip>
                      )}
                      {!h.connected && (
                        <Link to="/connect" className="link text-xs">
                          {h.tokenExpired ? "Reconnect" : "Connect"}
                        </Link>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => setEditingId(h.id)}>
                        Edit
                      </Button>
                    </div>
                  </div>
                  {h.members.length > 0 && (
                    <ul className="muted flex flex-col gap-1">
                      {h.members.map((m, i) => (
                        <li key={i}>
                          <span className="font-medium text-foreground">{m.name}</span>
                          {m.preferences && <span>: {m.preferences}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ),
            )}
          </ul>
        )}
      </GlassPanel>

      <GlassPanel>
        <h2 className="section-title mb-4">Create a household</h2>
        <form onSubmit={onSubmit} className="flex flex-col gap-4 sm:max-w-lg">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Flamingo" required />
          </Field>

          <Fieldset legend="Members (optional)" hint="Preferences are passed to the Chat agent.">
            <MemberRowsEditor members={members} onChange={setMembers} />
          </Fieldset>

          {formError && <ErrorBanner message={formError} />}
          <Button type="submit" variant="solid" disabled={submitting} className="self-start">
            {submitting ? "Creating…" : "Create household"}
          </Button>
        </form>
      </GlassPanel>
    </div>
  );
}
