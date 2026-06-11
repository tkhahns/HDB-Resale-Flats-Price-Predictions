import { NextResponse } from "next/server";
import { getAnalytics } from "@/lib/analytics";

export const revalidate = 3600;

export async function GET() {
  try {
    const data = await getAnalytics();
    return NextResponse.json(data);
  } catch (err) {
    console.error("analytics route error:", err);
    return NextResponse.json({ error: "Analytics unavailable" }, { status: 503 });
  }
}
