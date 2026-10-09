// Lists team members; no invite flow exists yet.
const members = [{ name: "Sample Member", email: "member@example.test", role: "admin" }];

export function Members() {
  return <ul>{members.map((m) => <li key={m.email}>{m.name} ({m.role})</li>)}</ul>;
}
