import { Icon } from "./Icon";

export function SDKSetup({ services }: { services: string[] }) {
  return (
    <section className="settings-section" id="sdk-setup">
      <div className="settings-intro">
        <span className="section-icon">
          <Icon name="code" size={20} />
        </span>
        <h2>Instrumentation</h2>
        <p>Bring your first service into view with the Python SDK.</p>
      </div>
      <div className="panel settings-content">
        <div className="section-heading">
          <h3>Instrument a FastAPI service</h3>
          <span className="badge">Python</span>
        </div>
        <p className="subtle">
          Install <code>sdk/python</code>, set <code>TRACELORE_API_KEY</code>,{" "}
          <code>TRACELORE_SERVICE</code>, and <code>TRACELORE_ENDPOINT</code>,
          then attach the ASGI middleware.
        </p>
        <pre>
          <code>{`from tracelore import Tracelore, load_config
from tracelore.integrations.fastapi import TraceloreMiddleware

client = Tracelore(load_config())
client.start()
app.add_middleware(TraceloreMiddleware, client=client)
# Call client.shutdown() in the application's lifespan teardown.`}</code>
        </pre>
        <div className="sdk-note">
          <Icon name="shield" size={16} />
          <p>
            Enable HTTP, asyncpg/SQLAlchemy, and Redis adapters to reconstruct
            dependency paths. Events contain hashes and metadata rather than
            request bodies or SQL.
          </p>
        </div>
        {services.length > 0 && (
          <div className="connected-services">
            <h3>Connected services</h3>
            <div>
              {services.map((service) => (
                <span className="badge" key={service}>
                  <Icon name="server" size={12} />
                  {service}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
