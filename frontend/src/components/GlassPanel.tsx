import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Alert } from "@/components/ui/alert";

/** The warm hairline card every page section sits in (ChaiUI `card-chai`).
 * Name kept from the earlier glass design so call sites didn't churn. */
export function GlassPanel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card-chai p-5 sm:p-6 ${className}`}>{children}</section>;
}

// Backend error strings that mean "go reconnect this household", e.g.
// _token_for's "...isn't connected to Swiggy yet -- visit /auth/login
// first" / "...connection has expired -- reconnect via /connect", and
// describe_mcp_failure's "...try reconnecting this household via
// /auth/login". They tell the user the right fix in words, but as plain
// text in a banner there was nothing to actually click -- add a real link
// wherever that pattern shows up, in the one shared component every page
// already uses for errors, instead of per-page special-casing.
const NEEDS_RECONNECT = /reconnect|isn't connected to swiggy/i;

/** Errors as a ChaiUI danger Alert (red outline and text, never a fill). */
export function ErrorBanner({ message }: { message: string }) {
  return (
    <Alert tone="danger">
      <p>{message}</p>
      {NEEDS_RECONNECT.test(message) && (
        <Link to="/connect" className="link mt-1 inline-block">
          Go to Connect Swiggy
        </Link>
      )}
    </Alert>
  );
}
