// Questions the agent leaves for the human, as `- <question> => <option> | <option>` lines in
// .iw-watch/questions.md. Each option becomes a `/iw <option>` comment to paste on the PR
// (Discord shows them, one copy box each); that comment is the next round's input (scan.mjs: type 'answer').
// The options are agent-written text, so they are cut down to plain characters.
const PLAIN = /[^\p{L}\p{N} .,:_/#+-]/gu;
const MAX_Q = 5;
const MAX_OPT = 4;

export function parseQuestions(text) {
  const out = [];
  for (const line of String(text || '').split('\n')) {
    const m = /^\s*-\s*(.+?)\s*=>\s*(.+)$/.exec(line);
    if (!m) continue;
    const options = m[2].split('|').map((o) => o.replace(PLAIN, ' ').replace(/\s+/g, ' ').trim().slice(0, 80)).filter(Boolean).slice(0, MAX_OPT);
    if (!options.length) continue;
    out.push({ q: m[1].replace(/[\u0000-\u001f\u007f]/g, ' ').slice(0, 200), options });
    if (out.length === MAX_Q) break;
  }
  return out;
}

/** The comments to paste on the PR, one per option: never a shell command */
export const answerComments = (options) => options.map((o) => `/iw ${o.replace(PLAIN, ' ')}`);

/** The text block for a notice: each question with the /iw comments that answer it */
export function questionsText(questions) {
  return questions.map((x) => `Q: ${x.q}\n${answerComments(x.options).map((c) => `  ${c}`).join('\n')}`).join('\n');
}
