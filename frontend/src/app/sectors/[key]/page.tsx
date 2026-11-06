import { Suspense } from "react";
import SectorPage from "./Client";

// Server wrapper: awaits route params inside Suspense (required by Next 16 for dynamic segments).
export default function Page({ params }: PageProps<"/sectors/[key]">) {
  return (
    <Suspense fallback={null}>
      <Resolved params={params} />
    </Suspense>
  );
}

async function Resolved({ params }: { params: PageProps<"/sectors/[key]">["params"] }) {
  const { key } = await params;
  return <SectorPage sectorKey={key} />;
}