import { redirect } from "next/navigation";

export default function WeeklyBriefPage() {
  // Weekly Brief content is folded into Gameweek Hub.
  redirect("/weekly");
}
