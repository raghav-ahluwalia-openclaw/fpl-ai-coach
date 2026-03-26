import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FPL AI Coach",
  description: "AI helper for Fantasy Premier League decisions",
};

const navItems = [
  { href: "/weekly", label: "Gameweek Hub" },
  { href: "/live", label: "Live" },
  { href: "/planner", label: "Planner" },
  { href: "/leagues", label: "Leagues" },
  { href: "/top", label: "Research" },
  { href: "/socials", label: "Social Intel" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <header className="sticky top-0 z-50 border-b border-white/15 bg-[#240033]/85 backdrop-blur-md">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-5 flex-wrap">
              <Link
                href="/"
                aria-label="Home"
                className="text-[#00ff87] hover:text-[#7effb8] transition-colors"
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
              <nav className="flex items-center gap-4 text-sm text-[#00ff87] flex-wrap">
                {navItems.map((item) => (
                  <Link key={item.href} href={item.href} className="hover:text-[#7effb8] transition-colors">
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>

            <div className="flex items-center gap-2 text-sm shrink-0">
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
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
