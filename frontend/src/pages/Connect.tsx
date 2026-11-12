import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "../api";
import { PageHead } from "../components/Chai";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";
import { useHousehold } from "../components/HouseholdContext";

export default function Connect() {
  const { households, error, reload } = useHousehold();
  const [params, setParams] = useSearchParams();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnectError, setDisconnectError] = useState<string | null>(null);
  const toast = useToast();

  const justConnectedId = params.get("connected") === "1" ? params.get("household_id") : null;
  const confirming = households?.find((h) => h.id === confirmingId) ?? null;

  useEffect(() => {
    if (justConnectedId) {
      reload();
      // Clear the query params so a refresh doesn't re-show the banner.
      setParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [justConnectedId]);

  function connect(householdId: number) {
    // Full-page redirect -- this has to leave the SPA: Swiggy's OAuth
    // callback lands on the FastAPI backend, not on this React app.
    window.location.href = `/auth/login/${householdId}?next=react`;
  }

  async function disconnect() {
    if (!confirming) return;
    setDisconnecting(true);
    setDisconnectError(null);
    try {
      await api.disconnectHousehold(confirming.id);
      setConfirmingId(null);
      toast(`${confirming.name} disconnected from Swiggy`, { tone: "success" });
      reload();
    } catch (err) {
      // Shown inside the dialog, so the person can retry or cancel.
      setDisconnectError(err instanceof ApiError ? err.message : "Could not disconnect");
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHead title="Connect Swiggy">
        Link a household to its <span className="highlight">Swiggy account</span> so Dineout, Instamart
        and Chat can act on its behalf.
      </PageHead>

      {justConnectedId && <Alert tone="success" title="Connected successfully" />}
      {error && <ErrorBanner message={error} />}

      <GlassPanel>
        {households === null ? (
          <Spinner label="Loading households" />
        ) : households.length === 0 ? (
          <p className="muted">No households yet. Create one on the Households page first.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {households.map((h) => (
              <li key={h.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <span className="flex items-center gap-2">
                  <span className="font-medium">{h.name}</span>
                  {h.connected ? (
                    <Chip tone="success">Connected</Chip>
                  ) : h.tokenExpired ? (
                    <Chip className="border-yellow-600/30 text-yellow-700 dark:border-yellow-400/30 dark:text-yellow-400">
                      Connection expired
                    </Chip>
                  ) : (
                    <Chip>Not connected</Chip>
                  )}
                </span>
                {h.connected ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setDisconnectError(null);
                      setConfirmingId(h.id);
                    }}
                  >
                    Disconnect
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => connect(h.id)}>
                    {h.tokenExpired ? "Reconnect to Swiggy" : "Connect to Swiggy"}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </GlassPanel>

      <ConfirmDialog
        open={confirming !== null}
        title={`Disconnect ${confirming?.name ?? "this household"} from Swiggy?`}
        confirmLabel="Disconnect"
        busyLabel="Disconnecting…"
        cancelLabel="Keep it connected"
        busy={disconnecting}
        error={disconnectError}
        onConfirm={disconnect}
        onCancel={() => setConfirmingId(null)}
      >
        <p>
          This removes the saved Swiggy sign-in for this household. Dineout, Instamart and Chat will stop
          working for it until someone connects it again.
        </p>
        <p className="mt-2">The household and its members are kept.</p>
      </ConfirmDialog>
    </div>
  );
}
