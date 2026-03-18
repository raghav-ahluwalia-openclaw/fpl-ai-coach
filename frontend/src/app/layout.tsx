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
  { href: "/", label: "Dashboard" },
  { href: "/global", label: "Global Picks" },
  { href: "/targets", label: "Target Radar" },
  { href: "/top", label: "Top Players" },
  { href: "/team", label: "My Team" },
  { href: "/team-rank", label: "Rank Trend" },
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
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-5 flex-wrap">
            <Link href="/" className="font-black tracking-wide text-[#00ff87]">
              FPL AI COACH
            </Link>
            <nav className="flex items-center gap-4 text-sm text-white/85">
              {navItems.map((item) => (
                <Link key={item.href} href={item.href} className="hover:text-[#00ff87] transition-colors">
                  {item.label}
                </Link>
              ))}
              <a
                href="/cdn-cgi/access/logout"
                className="ml-1 rounded-md border border-white/25 px-2 py-1 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition-colors"
              >
                Logout
              </a>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
