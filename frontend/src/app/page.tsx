import Link from "next/link";

const primaryCards = [
  {
    title: "Gameweek Hub",
    desc: "One screen per GW: team health, Plan A/B/C transfers, captain matrix, and key changes.",
    href: "/weekly",
  },
  {
    title: "Planner",
    desc: "Chip planning, rival intelligence, and weekly digest payloads.",
    href: "/planner",
  },
  {
    title: "Live Team",
    desc: "Track your in-progress GW score with starter/bench split and captain impact.",
    href: "/live",
  },
  {
    title: "Leagues",
    desc: "See your rank across leagues, gap-to-next, and rivalry insights.",
    href: "/leagues",
  },
  {
    title: "Research",
    desc: "Top picks, explainability cards, and captaincy analysis.",
    href: "/top",
  },
  {
    title: "Social Intel",
    desc: "YouTube creators + top Reddit FantasyPL threads with summaries, player mentions, and sentiment.",
    href: "/socials",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <section className="mb-6 sm:mb-8 rounded-2xl p-4 sm:p-6 md:p-8 border border-white/20 bg-gradient-to-r from-[#37003c] via-[#5f0f78] to-[#e90052] shadow-2xl relative overflow-hidden">
        <div className="relative z-10">
          <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/90 mb-2">Fantasy Premier League</p>
          <h1 className="text-3xl md:text-5xl font-black">FPL AI Coach</h1>
          <p className="text-sm md:text-lg text-white/85 mt-2 max-w-xl">
            Master your season with AI-driven insights. Focus on what matters most.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/weekly"
              className="bg-[#00ff87] text-[#37003c] px-6 py-3 rounded-xl font-black text-lg hover:bg-[#00e676] transition-all transform hover:scale-105 flex items-center gap-2"
            >
              Start Here: Weekly Hub
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                <path fillRule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z" clipRule="evenodd" />
              </svg>
            </Link>
          </div>
        </div>
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        {primaryCards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className={`rounded-2xl border p-5 transition-all ${
              card.href === "/weekly" 
                ? "border-[#00ff87] bg-[#00ff87]/5 ring-1 ring-[#00ff87]/20" 
                : "border-white/15 bg-white/5"
            } backdrop-blur-md hover:border-[#00ff87]/60 hover:bg-white/10`}
          >
            <div className="flex justify-between items-start mb-2">
              <h2 className="text-xl font-bold text-[#00ff87]">{card.title}</h2>
              {card.href === "/weekly" && (
                <span className="text-[10px] uppercase tracking-widest bg-[#00ff87] text-[#37003c] px-2 py-0.5 rounded font-black">Recommended</span>
              )}
            </div>
            <p className="text-white/80">{card.desc}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
