// Questions the agent leaves for the human, as `- <question> => <option> | <option>` lines in
// .iw-watch/questions.md. Each option becomes a command to copy from Discord into a terminal; the
// resulting `/iw <option>` comment is the next round's input (scan.mjs: type 'answer').
// The options are agent-written text that the human pastes into a shell, so they are cut down to plain
// characters and single-quoted: no quote, $, backtick, backslash or shell operator survives.
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

export const answerCommands = (pr, options) => options.map((o) => `gh pr comment ${Number(pr)} --body '/iw ${o.replace(PLAIN, ' ')}'`);

/** The text block for a notice: each question with its copy-paste answers */
export function questionsText(pr, questions) {
  return questions.map((x) => `Q: ${x.q}\n${answerCommands(pr, x.options).map((c) => `  ${c}`).join('\n')}`).join('\n');
}
