type Props = { children: string; busy?: boolean; onClick: () => void };

export function Button({ children, busy, onClick }: Props) {
  return (
    <button disabled={busy} aria-busy={busy} onClick={onClick}>
      {busy ? "Working..." : children}
    </button>
  );
}
