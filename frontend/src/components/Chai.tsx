import type { ReactNode } from "react";

/** App-specific bits on top of the @chaiui registry components in
 * components/ui and components/*.tsx (installed via components.json). */

/** Wordmark in Onest. The orange dot is one of the few places orange is
 * allowed (the logo). Not the registry's Logo, which is ChaiCode's own mark. */
export function Logo() {
  return (
    <span className="flex items-center gap-1 font-onest text-xl font-medium tracking-tight">
      Swiggy MCP
      <span className="size-1.5 translate-y-1 rounded-full bg-brand" aria-hidden="true" />
    </span>
  );
}

/** Centred page title plus a lead (put one `.highlight` phrase in it). */
export function PageHead({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-3">
      <h1 className="page-title">{title}</h1>
      <p className="page-lead">{children}</p>
    </div>
  );
}
