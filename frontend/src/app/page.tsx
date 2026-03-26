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
    title: "FPL Socials",
    desc: "YouTube Creators + top Reddit FantasyPL threads with summaries, player mentions, and sentiment.",
    href: "/socials",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <section className="mb-6 sm:mb-8 rounded-2xl p-4 sm:p-6 md:p-8 border border-white/20 bg-gradient-to-r from-[#37003c] via-[#5f0f78] to-[#e90052] shadow-2xl">
        <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/90 mb-2">Fantasy Premier League</p>
        <h1 className="text-3xl md:text-4xl font-black">FPL AI Coach</h1>
        <p className="text-sm md:text-base text-white/85 mt-2">
          Clean flow: start with Gameweek Hub, then refine in Planner and Research.
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

    </main>
  );
}
