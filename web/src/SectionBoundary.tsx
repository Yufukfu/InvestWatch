import { Component, type ReactNode } from 'react';

type Props = { fallback: ReactNode; children: ReactNode };

// Keeps a failing section (e.g. a lazy chunk that cannot load after a redeploy) from unmounting the whole app.
export class SectionBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
