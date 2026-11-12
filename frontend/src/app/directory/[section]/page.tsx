import type { Metadata } from "next";
import { DirectoryHub, hubMetadata, type SearchParams } from "@/components/directory/hub";

type Props = { params: Promise<{ section: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { section } = await params;
  return hubMetadata(section, undefined, await searchParams);
}

export default async function DirectorySectionPage({ params, searchParams }: Props) {
  const { section } = await params;
  return <DirectoryHub sectionSlug={section} searchParams={await searchParams} />;
}
