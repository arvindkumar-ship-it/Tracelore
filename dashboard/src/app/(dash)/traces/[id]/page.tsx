"use client";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { useParams } from "next/navigation";
import { PageHeading } from "@/components/QueryState";
import { TraceExplorer } from "@/components/TraceExplorer";
export default function TracePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <>
      <Link className="back-link" href="/incidents">
        <Icon name="arrowLeft" size={14} />
        Incident stream
      </Link>
      <PageHeading
        eyebrow="Recorded request"
        title="Trace explorer"
        description={`Trace ${id}`}
      />
      <TraceExplorer traceId={id} />
    </>
  );
}
