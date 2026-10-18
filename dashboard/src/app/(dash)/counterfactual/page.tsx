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
        eyebrow="04 / WHAT-IF LAB"
        title="Before you ship the fix."
        description="Explore timeout, cache, and latency changes against recorded traces. Every result is labeled as a simulation."
      />
      <Suspense fallback={<div className="panel skeleton" />}>
        <Lab />
      </Suspense>
    </>
  );
}
