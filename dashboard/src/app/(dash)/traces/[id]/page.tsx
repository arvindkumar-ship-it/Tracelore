"use client";
import { useParams } from "next/navigation";
import { PageHeading } from "@/components/QueryState";
import { TraceExplorer } from "@/components/TraceExplorer";
export default function TracePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <>
      <PageHeading
        eyebrow="REPLAY / TRACE"
        title="Follow the request."
        description={`Trace ${id}`}
      />
      <TraceExplorer traceId={id} />
    </>
  );
}
