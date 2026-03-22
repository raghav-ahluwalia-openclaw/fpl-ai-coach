import Link from "next/link";

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export default function WeeklyBriefPage() {
  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-4xl mx-auto text-white">
      <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black mb-4">Weekly Brief</h1>
      <section className={cardClass}>
        <p className="text-white/85">Weekly Brief and notification controls are currently disabled.</p>
        <p className="text-white/70 mt-2">Use Gameweek Hub for planning and FPL Socials for creator/reddit consensus.</p>
        <div className="mt-4 grid sm:flex gap-2 sm:gap-3">
          <Link href="/weekly" className="rounded-md px-4 py-2 bg-[#00ff87] text-[#37003c] font-bold text-center w-full sm:w-auto">
            Open Gameweek Hub
          </Link>
          <Link href="/socials" className="rounded-md px-4 h-10 border border-white/30 bg-black/30 text-white font-semibold text-center w-full sm:w-auto">
            Open FPL Socials
          </Link>
        </div>
      </section>
    </main>
  );
}
