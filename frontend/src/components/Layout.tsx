import { Link, Outlet, useLocation } from "react-router-dom";
import { Backdrop } from "@/components/backdrop";
import { Navbar } from "@/components/navbar";
import { Button } from "@/components/ui/button";
import { api } from "../api";
import { Logo } from "./Chai";
import { HouseholdProvider } from "./HouseholdContext";
import { HouseholdStrip } from "./HouseholdStrip";

// Pages that act for one household get the household strip above them.
const HOUSEHOLD_SCOPED = ["/", "/dineout", "/instamart", "/chat"];

const links = [
  { href: "/", label: "Home" },
  { href: "/households", label: "Households" },
  { href: "/connect", label: "Connect Swiggy" },
  { href: "/dineout", label: "Dineout" },
  { href: "/instamart", label: "Instamart" },
  { href: "/chat", label: "Chat" },
];

async function logout() {
  // Reload rather than lifting AuthGate's state down here -- simplest way
  // to get back to a clean "check /auth/session/me" pass after the cookie
  // is cleared, without threading auth state through the router tree.
  await api.logout().catch(() => {});
  window.location.reload();
}

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-svh flex-col">
      <Backdrop />

      {/* ChaiUI navbar, inline layout: links on lg+, folded into the menu
          button below that. Sticky, blurs only once the page scrolls. */}
      <Navbar
        layout="inline"
        logo={
          <Link to="/" aria-label="Home">
            <Logo />
          </Link>
        }
        groups={links.map((l) => ({
          label: l.label,
          href: l.href,
          active: l.href === "/" ? pathname === "/" : pathname.startsWith(l.href),
        }))}
        actions={
          <Button variant="ghost" size="sm" onClick={logout}>
            Log out
          </Button>
        }
      />

      <HouseholdProvider>
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 pt-2 pb-16 sm:px-12 sm:pt-4">
          {HOUSEHOLD_SCOPED.includes(pathname) && <HouseholdStrip />}
          <Outlet />
        </main>
      </HouseholdProvider>

      <footer className="relative px-6 py-6 text-center font-montserrat text-xs text-neutral-500 sm:px-12 before:absolute before:top-0 before:left-1/2 before:h-px before:w-full before:max-w-[1440px] before:-translate-x-1/2 before:bg-amber-600 before:opacity-10 before:[mask-image:linear-gradient(90deg,transparent_0%,black_40%,black_60%,transparent_100%)] dark:text-neutral-400 dark:before:bg-orange-300">
        Swiggy MCP Project
      </footer>
    </div>
  );
}
