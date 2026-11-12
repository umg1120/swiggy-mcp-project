import { useState } from "react";
import { Backdrop } from "@/components/backdrop";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "../api";
import { Logo } from "../components/Chai";
import { ErrorBanner, GlassPanel } from "../components/GlassPanel";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.login(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <Backdrop />
      <div className="absolute top-4 right-4">
        <ThemeSwitcher />
      </div>
      <GlassPanel className="w-full max-w-sm">
        <Logo />
        <p className="muted mt-3">
          Enter the app password to continue to <span className="highlight">your households</span>.
        </p>
        <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4">
          <Field label="Password">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              autoFocus
              required
            />
          </Field>
          {error && <ErrorBanner message={error} />}
          <Button type="submit" variant="solid" disabled={submitting} className="w-full">
            {submitting ? "Checking…" : "Log in"}
          </Button>
        </form>
      </GlassPanel>
    </div>
  );
}
