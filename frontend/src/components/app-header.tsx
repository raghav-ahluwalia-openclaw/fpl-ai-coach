"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

type NavItem = { href: string; label: string };
type NavPrimary = { href: string; label: string; isPrimary: true };
type NavGroup = { group: string; items: NavItem[] };

const navGroups: (NavPrimary | NavGroup)[] = [
  { href: "/weekly", label: "Weekly", isPrimary: true },
  {
    group: "Play",
    items: [{ href: "/live", label: "Live" }],
  },
  {
    group: "Plan",
    items: [
      { href: "/planner", label: "Planner" },
      { href: "/simulation", label: "Sim Lab" },
    ],
  },
  {
    group: "Research",
    items: [
      { href: "/top", label: "Analysis" },
      { href: "/socials", label: "Social" },
      { href: "/leagues", label: "Leagues" },
    ],
  },
];

function linkClass(active: boolean) {
  return active
    ? "text-[#37003c] bg-[#00ff87] rounded-md px-2 py-0.5"
    : "text-[#00ff87] hover:text-[#7effb8]";
}

export default function AppHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/15 bg-[#240033]/85 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            aria-label="Home"
            className="text-[#00ff87] hover:text-[#7effb8] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff87] rounded"
            title="Home"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6">
              <rect x="2.25" y="2.25" width="19.5" height="19.5" rx="5" ry="5" fill="none" stroke="currentColor" strokeWidth="1.75" />
              <path
                d="M12 7.2l5 4.3v6.1a1 1 0 0 1-1 1h-2.8a1 1 0 0 1-1-1v-2.8h-1.4v2.8a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1v-6.1l5-4.3z"
                fill="currentColor"
              />
            </svg>
          </Link>
          <span className="hidden sm:inline text-white/70 text-sm">FPL AI Coach</span>
        </div>

        <nav className="hidden md:flex items-center gap-6 text-sm">
          {navGroups.map((group) => {
            if ("isPrimary" in group && group.isPrimary) {
              const active = pathname === group.href;
              return (
                <Link
                  key={group.href}
                  href={group.href}
                  aria-current={active ? "page" : undefined}
                  className={`${linkClass(active)} text-base font-black transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff87]`}
                >
                  {group.label}
                </Link>
              );
            }

            if ("group" in group) {
              return (
                <div key={group.group} className="flex items-center gap-2 border-l border-white/10 pl-4">
                  <span className="text-white/40 text-[10px] uppercase tracking-widest font-bold">{group.group}</span>
                  <div className="flex items-center gap-3">
                    {group.items.map((item) => {
                      const active = pathname === item.href;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          className={`${linkClass(active)} transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00ff87]`}
                        >
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            }

            return null;
          })}
        </nav>

        <div className="hidden md:flex items-center gap-2 text-sm shrink-0">
          <Link
            href="/settings"
            className="rounded-md border border-white/25 px-2 py-1 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition-colors"
          >
            Settings
          </Link>
          <a
            href="/cdn-cgi/access/logout"
            className="rounded-md border border-white/25 px-2 py-1 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition-colors"
          >
            Logout
          </a>
        </div>

        <button
          type="button"
          className="md:hidden rounded-md border border-white/25 px-3 py-1 text-white/90"
          aria-label="Open navigation menu"
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      {open ? (
        <div id="mobile-nav" className="md:hidden border-t border-white/10 px-4 py-3 bg-[#220030]">
          <nav className="grid gap-4 text-sm">
            {navGroups.map((group) => {
              if ("isPrimary" in group && group.isPrimary) {
                const active = pathname === group.href;
                return (
                  <Link
                    key={group.href}
                    href={group.href}
                    aria-current={active ? "page" : undefined}
                    onClick={() => setOpen(false)}
                    className={`${active ? "text-[#37003c] bg-[#00ff87]" : "text-[#00ff87] bg-black/20"} rounded-md px-3 py-2 text-lg font-black`}
                  >
                    {group.label}
                  </Link>
                );
              }

              if ("group" in group) {
                return (
                  <div key={group.group} className="grid gap-2">
                    <span className="text-white/40 text-[10px] uppercase tracking-widest font-bold px-3">{group.group}</span>
                    <div className="grid gap-2">
                      {group.items.map((item) => {
                        const active = pathname === item.href;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            aria-current={active ? "page" : undefined}
                            onClick={() => setOpen(false)}
                            className={`${active ? "text-[#37003c] bg-[#00ff87]" : "text-[#00ff87] bg-black/20"} rounded-md px-3 py-2`}
                          >
                            {item.label}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                );
              }

              return null;
            })}
          </nav>
          <div className="mt-3 flex gap-2">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="rounded-md border border-white/25 px-3 py-2 text-white/90"
            >
              Settings
            </Link>
            <a
              href="/cdn-cgi/access/logout"
              className="rounded-md border border-white/25 px-3 py-2 text-white/90"
            >
              Logout
            </a>
          </div>
        </div>
      ) : null}
    </header>
  );
}
