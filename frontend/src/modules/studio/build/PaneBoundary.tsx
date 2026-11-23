"use client";

import { Component, type ReactNode } from "react";

/** Keeps a crash inside one pane (chart, panel) instead of blanking the Build page; Retry remounts it. */
export class PaneBoundary extends Component<{ name: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error(`[${this.props.name}]`, error); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="dv-empty" role="alert">
        <p>{this.props.name} hit an error: {this.state.error.message}</p>
        <button type="button" className="btn sm" onClick={() => this.setState({ error: null })}>Retry</button>
      </div>
    );
  }
}
