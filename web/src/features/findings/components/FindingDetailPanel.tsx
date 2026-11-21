import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { FindingDetail, RuleView, Severity } from '../model';
import {
  formatUtc,
  METHOD_LABEL,
  MODULE_LABEL,
  platformLabel,
  REGISTRY_LABEL,
  safeHttpUrl,
  SEVERITY_LABEL,
  STATUS_LABEL,
} from './labels';
import { RiskBadge } from './RiskBadge';

type Props = {
  detail: FindingDetail | undefined;
  isLoading: boolean;
  isError: boolean;
  notFound: boolean;
  onClose: () => void;
  statusEditor?: ReactNode;
};

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

const SEVERITY_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

function IssueItem({ rule, signal }: { rule: RuleView; signal: boolean }) {
  const verdict = rule.result === 'uncertain' ? 'Niepewne' : signal ? 'Wykryto sygnał' : 'Niespełniona';
  return (
    <li className={`rule rule-${rule.result} sev-${rule.severity}`}>
      <div className="rule-head">
        <span className="rule-id">{rule.ruleId}</span>
        <span className="rule-name">{rule.name}</span>
        <span className={`rule-verdict verdict-${rule.result}`}>{verdict}</span>
      </div>
      <p className="rule-meta">
        Waga: {SEVERITY_LABEL[rule.severity] ?? rule.severity}
        {rule.method && <> · Metoda: {METHOD_LABEL[rule.method] ?? rule.method}</>}
      </p>
      {rule.explanation && <p className="rule-explanation">{rule.explanation}</p>}
      {rule.evidence && (
        <blockquote className="rule-evidence">
          <span className="sr-label">Cytat z materiału: </span>„{rule.evidence}”
        </blockquote>
      )}
      {rule.legalBasis && (
        <p className="rule-legal">
          <strong>Podstawa prawna:</strong> {rule.legalBasis}
        </p>
      )}
    </li>
  );
}

function RuleGroup({ title, rules }: { title: string; rules: RuleView[] }) {
  if (rules.length === 0) return null;
  return (
    <details className="rule-group">
      <summary>
        {title} ({rules.length})
      </summary>
      <ul>
        {rules.map((r) => (
          <li key={r.ruleId}>
            <span className="rule-id">{r.ruleId}</span> {r.name}
            {r.explanation && <span className="muted"> – {r.explanation}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Screenshot({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <p className="muted">Nie udało się wczytać zrzutu ekranu.</p>;
  return <img className="shot" src={src} alt="Zrzut ekranu materiału (desktop)" loading="lazy" onError={() => setFailed(true)} />;
}

function Body({ d, statusEditor }: { d: FindingDetail; statusEditor?: ReactNode }) {
  const signal = d.module !== 'M2';
  const issues = d.rules
    .filter((r) => r.result === 'fail' || r.result === 'uncertain')
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3));
  const passed = d.rules.filter((r) => r.result === 'pass');
  const notApplicable = d.rules.filter((r) => r.result === 'not_applicable');
  const href = safeHttpUrl(d.url);
  const profile = safeHttpUrl(d.advertiser?.profileUrl);
  // Screenshots are served by the API itself; never load an image from elsewhere.
  const shot = d.screenshotUrl?.startsWith('/api/') ? d.screenshotUrl : undefined;
  const issuesTitle = signal ? 'Sygnały ryzyka' : 'Naruszenia i niepewne wyniki';

  return (
    <>
      <dl className="facts">
        <div>
          <dt>Ryzyko</dt>
          <dd>
            <RiskBadge level={d.riskLevel} />
          </dd>
        </div>
        <div>
          <dt>Wynik</dt>
          <dd>{d.score.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Moduł</dt>
          <dd>
            {d.module} · {MODULE_LABEL[d.module]}
          </dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{STATUS_LABEL[d.status] ?? d.status}</dd>
        </div>
        <div>
          <dt>Platforma</dt>
          <dd>{platformLabel(d.platform)}</dd>
        </div>
        <div>
          <dt>Wykryto</dt>
          <dd>{formatUtc(d.detectedAt)}</dd>
        </div>
      </dl>
      <p className="source">
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer">
            Otwórz źródło ↗
          </a>
        ) : (
          <span className="muted">{d.url}</span>
        )}
      </p>

      {d.summary && (
        <section className="detail-section" aria-labelledby="d-summary">
          <h3 id="d-summary">Dlaczego to zgłoszenie</h3>
          <p>{d.summary}</p>
        </section>
      )}

      <section className="detail-section" aria-labelledby="d-issues">
        <h3 id="d-issues">
          {issuesTitle} ({issues.length})
        </h3>
        {issues.length === 0 ? (
          <p className="muted">Brak naruszeń ani niepewnych wyników.</p>
        ) : (
          <ul className="rules">
            {issues.map((r) => (
              <IssueItem key={r.ruleId} rule={r} signal={signal} />
            ))}
          </ul>
        )}
      </section>

      {passed.length + notApplicable.length > 0 && (
        <section className="detail-section" aria-label="Pozostałe wyniki">
          <RuleGroup title="Spełnione" rules={passed} />
          <RuleGroup title="Nie dotyczy" rules={notApplicable} />
        </section>
      )}

      {statusEditor && (
        <section className="detail-section" aria-labelledby="d-status">
          <h3 id="d-status">Decyzja analityka</h3>
          {statusEditor}
        </section>
      )}

      {(d.firm || d.advertiser) && (
        <section className="detail-section" aria-labelledby="d-parties">
          <h3 id="d-parties">Podmioty</h3>
          {d.firm && (
            <div className="party">
              <p className="party-name">{d.firm.name}</p>
              {d.firm.authorized !== undefined && (
                <p className={d.firm.authorized ? 'flag flag-ok' : 'flag flag-bad'}>
                  {d.firm.authorized ? 'Firma w rejestrze KNF' : 'Firma spoza rejestru KNF'}
                </p>
              )}
              {d.firm.registryType && <p className="muted">Typ: {REGISTRY_LABEL[d.firm.registryType] ?? d.firm.registryType}</p>}
              {d.firm.matchConfidence !== undefined && (
                <p className="muted">Pewność dopasowania: {Math.round(d.firm.matchConfidence * 100)}%</p>
              )}
            </div>
          )}
          {d.advertiser && (
            <div className="party">
              <p className="party-name">{d.advertiser.name ?? 'Nadawca bez nazwy'}</p>
              {d.advertiser.handle &&
                (profile ? (
                  <a href={profile} target="_blank" rel="noopener noreferrer">
                    {d.advertiser.handle}
                  </a>
                ) : (
                  <p>{d.advertiser.handle}</p>
                ))}
              {d.advertiser.inRegistry === false && <p className="flag flag-bad">Nadawca spoza rejestru KNF</p>}
              {d.advertiser.onWarningList && <p className="flag flag-bad">Na liście ostrzeżeń KNF</p>}
            </div>
          )}
        </section>
      )}

      {(d.excerpt || d.documentText) && (
        <section className="detail-section" aria-labelledby="d-content">
          <h3 id="d-content">Treść materiału</h3>
          {d.excerpt && <p className="excerpt">{d.excerpt}</p>}
          {d.documentText && d.documentText !== d.excerpt && (
            <details className="rule-group">
              <summary>Pełna treść</summary>
              <p className="excerpt">{d.documentText}</p>
            </details>
          )}
        </section>
      )}

      {shot && (
        <section className="detail-section" aria-labelledby="d-shot">
          <h3 id="d-shot">Zrzut ekranu</h3>
          <Screenshot src={shot} />
        </section>
      )}

      <p className="muted detail-footer">
        Analiza: {d.llm ? `model ${d.llm}` : 'tryb regułowy (bez modelu językowego)'}
        {d.pipelineVersion && <> · wersja {d.pipelineVersion}</>}
      </p>
    </>
  );
}

// Side panel with the finding detail. Scraped text is rendered as React text only.
export function FindingDetailPanel({ detail, isLoading, isError, notFound, onClose, statusEditor }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);

  // Modal: everything outside the panel is inert and the page does not scroll while it is open.
  // Focus moves into the panel on open and back to where it was on close. One effect, so the cleanup
  // lifts `inert` before restoring focus: browsers ignore focus() inside an inert subtree.
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const panel = panelRef.current;
    const others = Array.from(document.body.children).filter(
      (el): el is HTMLElement => el instanceof HTMLElement && !el.contains(panel) && !el.hasAttribute('inert'),
    );
    others.forEach((el) => el.setAttribute('inert', ''));
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      others.forEach((el) => el.removeAttribute('inert'));
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);

  // Escape closes from anywhere. In a field that holds text the first Escape only moves focus to
  // `Zamknij` (the text is kept); the next one closes.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      const t = e.target;
      if ((t instanceof HTMLTextAreaElement || t instanceof HTMLInputElement) && t.value !== '') {
        closeRef.current?.focus();
        return;
      }
      onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  let content: ReactNode;
  if (notFound) content = <p role="alert">To zgłoszenie nie istnieje.</p>;
  else if (isError && detail)
    content = (
      <>
        <p role="alert">Nie udało się odświeżyć szczegółów; pokazano ostatnio pobrane dane.</p>
        <Body d={detail} statusEditor={statusEditor} />
      </>
    );
  else if (isError) content = <p role="alert">Nie udało się pobrać szczegółów zgłoszenia.</p>;
  else if (isLoading || !detail) content = <p className="muted" role="status">Ładowanie szczegółów…</p>;
  else content = <Body d={detail} statusEditor={statusEditor} />;

  return (
    <aside
      ref={panelRef}
      className="detail"
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
      onKeyDown={(e) => {
        // Modal: Tab cycles inside the panel, the page behind the backdrop is out of reach.
        if (e.key !== 'Tab' || !panelRef.current) return;
        const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }}
    >
      <div className="detail-header">
        <h2 id="detail-title">{detail && !notFound ? detail.title : 'Szczegóły zgłoszenia'}</h2>
        <button ref={closeRef} type="button" className="btn" onClick={onClose}>
          Zamknij
        </button>
      </div>
      {content}
    </aside>
  );
}
