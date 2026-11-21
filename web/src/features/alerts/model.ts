export type Connection = 'connecting' | 'live' | 'offline';

// A high-risk toast. Built from the event payload `{ id, module, score, title, url, platform }`.
export type AlertItem = { id: string; title: string; module: 'M1' | 'M2' | 'M3' | undefined; score: number | undefined };
