import { AnalyticsData } from "./types";

const ANALYTICS_URL = process.env.ANALYTICS_JSON_URL;
const ARTIFACTS_BUCKET = process.env.AVM_ARTIFACTS_BUCKET;
const AWS_REGION = process.env.AWS_REGION ?? "ap-southeast-1";

async function fetchFromS3(): Promise<AnalyticsData> {
  const { S3Client, GetObjectCommand, ListObjectsV2Command } = await import("@aws-sdk/client-s3");
  const client = new S3Client({ region: AWS_REGION });

  // Resolve the latest run date from latest.json
  const latestObj = await client.send(
    new GetObjectCommand({ Bucket: ARTIFACTS_BUCKET, Key: "models/latest.json" })
  );
  const latestText = await latestObj.Body!.transformToString();
  const latest = JSON.parse(latestText) as { reports_prefix: string };

  // Strip s3://bucket/ prefix to get the S3 key
  const prefix = latest.reports_prefix.replace(/^s3:\/\/[^/]+\//, "");
  const key = `${prefix}/analytics.json`;

  const obj = await client.send(new GetObjectCommand({ Bucket: ARTIFACTS_BUCKET, Key: key }));
  const text = await obj.Body!.transformToString();
  return JSON.parse(text) as AnalyticsData;
}

async function fetchFromUrl(url: string): Promise<AnalyticsData> {
  const res = await fetch(url, { next: { revalidate: 3600 } });
  if (!res.ok) throw new Error(`Failed to fetch analytics: ${res.status}`);
  return res.json() as Promise<AnalyticsData>;
}

export async function getAnalytics(): Promise<AnalyticsData> {
  if (ANALYTICS_URL) return fetchFromUrl(ANALYTICS_URL);
  if (ARTIFACTS_BUCKET) return fetchFromS3();
  // Fall back to local file for development
  const path = await import("path");
  const fs = await import("fs/promises");
  const localPath = path.join(process.cwd(), "..", "reports", "analytics.json");
  const text = await fs.readFile(localPath, "utf-8");
  return JSON.parse(text) as AnalyticsData;
}
