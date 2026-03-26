import { redirect } from "next/navigation";

export default function CaptaincyPage() {
  // Captain deep-dive is consolidated into Research Hub.
  redirect("/top");
}
