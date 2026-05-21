import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail-page";
import { dashboardData, getDetailPage } from "@/lib/dashboard-data";

export function generateStaticParams() {
  return dashboardData.details.map((detail) => ({
    slug: detail.slug
  }));
}

export async function generateMetadata({
  params
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const detail = getDetailPage(slug);

  return {
    title: detail ? `${detail.title} | CAMELS dashboard` : "CAMELS detail"
  };
}

export default async function DetailRoute({
  params
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const detail = getDetailPage(slug);

  if (!detail) {
    notFound();
  }

  return <DetailPage detail={detail} />;
}
