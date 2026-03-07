"use client";

import { Component, ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; message: string; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="min-h-screen bg-gray-950 flex flex-col items-center justify-center text-white gap-4 px-6">
          <div className="text-4xl">⚠️</div>
          <p className="text-red-400 font-medium">Something went wrong</p>
          <p className="text-gray-500 text-sm text-center max-w-sm">{this.state.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 px-5 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition"
          >
            Reload
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
