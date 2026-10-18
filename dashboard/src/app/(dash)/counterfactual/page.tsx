"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CounterfactualPanel } from "@/components/CounterfactualPanel";
import { PageHeading } from "@/components/QueryState";
function Lab() {
  const params = useSearchParams();
  return (
    <CounterfactualPanel incidentId={params.get("incident") ?? undefined} />
  );
}
export default function CounterfactualPage() {
  return (
    <>
      <PageHeading
        eyebrow="Deterministic simulation"
        title="What-if lab"
        description="Test a hypothesis against recorded traces. See the possible outcome before you ship the fix."
      />
      <Suspense fallback={<div className="panel skeleton" />}>
        <Lab />
      </Suspense>
    </>
  );
}
