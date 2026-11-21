// Round cap. Every comment or issue body an iw-watch agent writes ends with MARKER, so the count
// lives on GitHub: a wiped state file or a second laptop cannot reset it. The sessions the runner
// recorded back it up for an agent that forgot the marker. Two watchers answering each other stop at the cap.
export const MARKER = '<!-- iw-watch -->';

export function countRounds({ comments, me, sessions = 0 }) {
  const mine = comments.filter((c) => c.user?.login?.toLowerCase() === me.toLowerCase() && String(c.body || '').includes(MARKER)).length;
  return Math.max(mine, sessions);
}

export const capReached = (rounds, max) => rounds >= max;
