import { useId, type ReactNode } from "react";

interface Common {
  label: string;
  hint?: ReactNode;
  required?: boolean;
  wide?: boolean;
}

function Label({ id, label, required }: { id: string; label: string; required?: boolean }) {
  return (
    <label className="field-label" htmlFor={id}>
      {label}
      {required ? (
        <span className="field-required" aria-hidden="true">
          {" "}
          *
        </span>
      ) : null}
    </label>
  );
}

function Hint({ id, hint }: { id: string; hint?: ReactNode }) {
  return hint ? (
    <p className="field-hint" id={id}>
      {hint}
    </p>
  ) : null;
}

export function TextField({
  label,
  hint,
  required,
  wide,
  value,
  onChange,
  type = "text",
  placeholder,
  autoFocus,
}: Common & {
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "url" | "search" | "date";
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const id = useId();
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <Label id={id} label={label} required={required} />
      <input
        id={id}
        className="input"
        type={type}
        value={value}
        placeholder={placeholder}
        required={required}
        aria-describedby={hint ? `${id}-hint` : undefined}
        data-autofocus={autoFocus ? "" : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      <Hint id={`${id}-hint`} hint={hint} />
    </div>
  );
}

export function NumberField({
  label,
  hint,
  required,
  wide,
  value,
  onChange,
  min = 1,
  max,
}: Common & { value: number | null; onChange: (value: number | null) => void; min?: number; max?: number }) {
  const id = useId();
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <Label id={id} label={label} required={required} />
      <input
        id={id}
        className="input"
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value ?? ""}
        required={required}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      />
      <Hint id={`${id}-hint`} hint={hint} />
    </div>
  );
}

export function SelectField({
  label,
  hint,
  required,
  wide,
  value,
  onChange,
  options,
  placeholder = "Choose…",
}: Common & {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <Label id={id} label={label} required={required} />
      <select
        id={id}
        className="select"
        value={value}
        required={required}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <Hint id={`${id}-hint`} hint={hint} />
    </div>
  );
}

export function TextArea({
  label,
  hint,
  wide = true,
  value,
  onChange,
  rows = 6,
  placeholder,
}: Common & { value: string; onChange: (value: string) => void; rows?: number; placeholder?: string }) {
  const id = useId();
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <Label id={id} label={label} />
      <textarea
        id={id}
        className="textarea"
        rows={rows}
        value={value}
        placeholder={placeholder}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      <Hint id={`${id}-hint`} hint={hint} />
    </div>
  );
}

export function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <div className="toggle-row field-wide">
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <div className="field">
        <label className="field-label" htmlFor={id}>
          {label}
        </label>
        {hint ? <p className="field-hint">{hint}</p> : null}
      </div>
    </div>
  );
}

/** A server error, shown where the action was. */
export function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <p className="field-error" role="alert">
      {message}
    </p>
  );
}
