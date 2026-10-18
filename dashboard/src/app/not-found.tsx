import Link from "next/link";
import { Brand } from "@/components/Brand";
import { Icon } from "@/components/Icon";
export default function NotFound() {
  return (
    <div className="route-fallback">
      <Link href="/incidents" aria-label="Tracelore home">
        <Brand />
      </Link>
      <main>
        <span className="empty-icon">
          <Icon name="search" size={24} />
        </span>
        <div className="eyebrow">404 · Page not found</div>
        <h1>This page is out of view.</h1>
        <p>
          The address may have changed, or the page no longer exists. Your
          observatory is just a step away.
        </p>
        <Link className="button" href="/incidents">
          <Icon name="arrowLeft" size={15} />
          Back to incidents
        </Link>
      </main>
    </div>
  );
}
