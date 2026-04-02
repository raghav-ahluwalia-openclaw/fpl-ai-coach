import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

function readEnvValueFromBackend(name: string): string {
  try {
    const envPath = path.resolve(process.cwd(), "..", "backend", ".env");
    if (!fs.existsSync(envPath)) return "";
    const raw = fs.readFileSync(envPath, "utf-8");
    const line = raw
      .split(/\r?\n/)
      .find((ln) => ln.trim().startsWith(`${name}=`));
    if (!line) return "";
    return line.split("=").slice(1).join("=").trim().replace(/^['\"]|['\"]$/g, "");
  } catch {
    return "";
  }
}

export async function POST(req: Request) {
  const backendOrigin = (
    process.env.BACKEND_ORIGIN ||
    new URL(req.url).origin
  ).replace(/\/$/, "");
  const adminToken =
    process.env.FPL_ADMIN_API_KEY ||
    process.env.ADMIN_API_KEY ||
    readEnvValueFromBackend("ADMIN_API_KEY");

  if (!adminToken) {
    return NextResponse.json(
      { error: "Server configuration missing: FPL_ADMIN_API_KEY or ADMIN_API_KEY is required for socials refresh." },
      { status: 503 },
    );
  }

  const backendUrl = `${backendOrigin}/api/fpl/socials/refresh?videos_per_creator=4`;

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "X-Admin-Token": adminToken,
        "Content-Type": "application/json",
      },
    });

    const body = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";

    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": contentType },
    });
  } catch {
    return NextResponse.json({ error: "Failed to connect to backend service" }, { status: 502 });
  }
}
