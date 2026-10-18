import { Icon } from "./Icon";

export function QueryState({
  loading,
  error,
  retry,
}: {
  loading?: boolean;
  error?: Error | null;
  retry?: () => void;
}) {
  if (error)
    return (
      <div role="alert" className="query-error">
        <Icon name="incidents" size={20} />
        <div>
          <h3>Could not load this view</h3>
          <p>{error.message}</p>
        </div>
        {retry && (
          <button className="secondary" onClick={retry}>
            <Icon name="refresh" size={15} />
            Try again
          </button>
        )}
      </div>
    );
  if (loading)
    return (
      <div className="panel skeleton" role="status" aria-label="Loading">
        <span className="sr-only">Loading this view…</span>
        <div />
        <div />
        <div />
      </div>
    );
  return null;
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="heading-action">{action}</div>}
    </div>
  );
}
