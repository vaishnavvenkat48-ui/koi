import { Suspense } from "react";
import SavedReportPage from "./Client";

// Server wrapper: awaits route params inside Suspense (required by Next 16 for dynamic segments).
export default function Page({ params }: PageProps<"/reports/[id]">) {
  return (
    <Suspense fallback={null}>
      <Resolved params={params} />
    </Suspense>
  );
}

async function Resolved({ params }: { params: PageProps<"/reports/[id]">["params"] }) {
  const { id } = await params;
  return <SavedReportPage id={id} />;
}