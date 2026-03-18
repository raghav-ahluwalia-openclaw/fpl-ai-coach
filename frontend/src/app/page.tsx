import Link from "next/link";

const primaryCards = [
  {
    title: "Weekly Brief",
    desc: "One-page final plan with captain, transfer, and consensus rationale.",
    href: "/brief",
  },
  {
    title: "My Team Hub",
    desc: "Import your squad, get personalized recommendations, and track rank trend.",
    href: "/team",
  },
  {
    title: "Planner",
    desc: "Chip planning, rival intelligence, and weekly digest payloads.",
    href: "/planner",
  },
  {
    title: "Insights",
    desc: "Top picks, explainability cards, and captaincy analysis.",
    href: "/top",
  },
];

const secondaryLinks = [
  { label: "Transfer Center", href: "/targets" },
  { label: "Captaincy Lab", href: "/captaincy" },
  { label: "Rank Trend", href: "/team-rank" },
  { label: "Global Picks", href: "/global" },
];

export default function Home() {
  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <section className="mb-8 rounded-2xl p-6 md:p-8 border border-white/20 bg-gradient-to-r from-[#37003c] via-[#5f0f78] to-[#e90052] shadow-2xl">
        <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/90 mb-2">Fantasy Premier League</p>
        <h1 className="text-3xl md:text-4xl font-black">FPL AI Coach</h1>
        <p className="text-sm md:text-base text-white/85 mt-2">
          Clean flow: start with Weekly Brief, then refine in My Team and Planner.
        </p>
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        {primaryCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5 hover:border-[#00ff87]/60 hover:bg-white/10 transition"
          >
            <h2 className="text-xl font-bold mb-2 text-[#00ff87]">{card.title}</h2>
            <p className="text-white/80">{card.desc}</p>
          </Link>
        ))}
      </section>

      <section className="mt-5 rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4">
        <p className="text-xs uppercase tracking-widest text-white/60 mb-2">Advanced tools</p>
        <div className="flex flex-wrap gap-2 text-sm">
          {secondaryLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-full px-3 py-1 border border-white/20 hover:border-[#00ff87]/60 hover:text-[#00ff87] transition"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
