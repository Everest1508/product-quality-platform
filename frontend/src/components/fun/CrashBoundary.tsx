import { Component, type ReactNode } from 'react';
import { RefreshIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';

// A page that throws shows a calm message and a retry instead of a blank screen. Keyed by the path, so moving elsewhere resets it.
export class CrashBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto flex max-w-sm flex-col items-center gap-4 py-20 text-center">
        <h1 className="text-xl font-semibold">Something went wrong on this page</h1>
        <p className="text-sm text-muted-foreground">It’s not you. Your work is safe. Try again, and if it keeps happening, tell your admin.</p>
        <Button onClick={() => this.setState({ failed: false })}><RefreshIcon />Try again</Button>
      </div>
    );
  }
}
