"use client";
import { useState } from "react";
import { Icon } from "./Icon";

export function NewKeyNotice({
  value,
  onDismiss,
}: {
  value: string;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="new-key" role="status">
      <div className="section-heading">
        <h3>
          <Icon name="check" size={15} />
          Your key is ready
        </h3>
        <button
          className="icon-button"
          aria-label="Dismiss new key"
          onClick={onDismiss}
        >
          <Icon name="close" size={15} />
        </button>
      </div>
      <p>
        Copy it now and store it as <code>TRACELORE_API_KEY</code>.
      </p>
      <pre>{value}</pre>
      <button
        className="secondary compact"
        onClick={() => {
          void navigator.clipboard
            .writeText(value)
            .then(() => {
              setCopied(true);
              setError("");
            })
            .catch(() =>
              setError(
                "Clipboard access is unavailable. Select the key above to copy it manually.",
              ),
            );
        }}
      >
        <Icon name={copied ? "check" : "copy"} size={14} />
        {copied ? "Copied" : "Copy key"}
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  );
}
