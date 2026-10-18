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
      <div role="alert" className="panel error">
        <h3>Could not load this view</h3>
        <p>{error.message}</p>
        <button className="ghost" onClick={retry}>
          Try again
        </button>
      </div>
    );
  if (loading) return <div className="panel skeleton" aria-label="Loading" />;
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
      {action}
    </div>
  );
}
