import { NextRequest, NextResponse } from "next/server";

const AVM_API_URL = process.env.AVM_API_URL;
const AVM_API_KEY = process.env.AVM_API_KEY;

export async function POST(req: NextRequest) {
  if (!AVM_API_URL) {
    return NextResponse.json({ error: "AVM_API_URL not configured" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (AVM_API_KEY) headers["X-Api-Key"] = AVM_API_KEY;

    const upstream = await fetch(`${AVM_API_URL}/predict`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    console.error("predict proxy error:", err);
    return NextResponse.json({ error: "Prediction service unavailable" }, { status: 503 });
  }
}
