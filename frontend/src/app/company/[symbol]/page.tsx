import { Suspense } from "react";
import CompanyPage from "./Client";

// Server wrapper: awaits route params inside Suspense (required by Next 16 for dynamic segments).
export default function Page({ params }: PageProps<"/company/[symbol]">) {
  return (
    <Suspense fallback={null}>
      <Resolved params={params} />
    </Suspense>
  );
}

async function Resolved({ params }: { params: PageProps<"/company/[symbol]">["params"] }) {
  const { symbol } = await params;
  return <CompanyPage symbol={symbol} />;
}