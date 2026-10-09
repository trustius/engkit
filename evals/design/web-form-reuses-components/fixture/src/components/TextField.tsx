type Props = { label: string; value: string; error?: string; onChange: (v: string) => void };

export function TextField({ label, value, error, onChange }: Props) {
  return (
    <label>
      {label}
      <input value={value} aria-invalid={!!error} onChange={(e) => onChange(e.target.value)} />
      {error && <span role="alert">{error}</span>}
    </label>
  );
}
