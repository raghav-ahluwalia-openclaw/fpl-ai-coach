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
  { href: "/brief", label: "Weekly Brief" },
  { href: "/team", label: "My Team" },
  { href: "/planner", label: "Planner" },
  { href: "/top", label: "Research" },
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
                className="text-white/85 text-xl leading-none hover:text-white transition-colors"
                title="Home"
              >
                ⌂
              </Link>
              <nav className="flex items-center gap-4 text-sm text-white/85 flex-wrap">
                {navItems.map((item) => (
                  <Link key={item.href} href={item.href} className="hover:text-[#00ff87] transition-colors">
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
