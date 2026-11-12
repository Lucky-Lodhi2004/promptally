import type { Metadata } from "next";
import { DirectoryHub, hubMetadata, type SearchParams } from "@/components/directory/hub";

type Props = { params: Promise<{ section: string; category: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { section, category } = await params;
  return hubMetadata(section, category, await searchParams);
}

export default async function DirectoryCategoryPage({ params, searchParams }: Props) {
  const { section, category } = await params;
  return <DirectoryHub sectionSlug={section} categorySlug={category} searchParams={await searchParams} />;
}
