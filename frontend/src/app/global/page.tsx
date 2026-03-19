import { redirect } from "next/navigation";

export default function GlobalPage() {
  // Global Picks page retired; use Research instead.
  redirect("/top");
}
