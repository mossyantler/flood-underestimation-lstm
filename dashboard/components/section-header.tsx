"use client";
import { useState } from "react";

interface SectionHeaderProps {
  title: string;
  route: string;
  csvContent: string;
  csvFilename: string;
}

export function SectionHeader({ title, route, csvContent, csvFilename }: SectionHeaderProps) {
  const [syncState, setSyncState] = useState<"idle" | "syncing" | "done">("idle");

  function handleSync() {
    setSyncState("syncing");
    setTimeout(() => {
      setSyncState("done");
      setTimeout(() => setSyncState("idle"), 2000);
    }, 600);
  }

  function handleExport() {
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = csvFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const syncLabel =
    syncState === "syncing" ? "동기화 중…" :
    syncState === "done" ? `✓ ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}` :
    "동기화";

  return (
    <div className="canvas-header">
      <div className="canvas-header-left">
        <span className="canvas-title">{title}</span>
        <span className="canvas-route">{route}</span>
      </div>
      <div className="canvas-header-right">
        <button
          type="button"
          className="btn-ghost"
          onClick={handleSync}
          disabled={syncState === "syncing"}
          style={syncState === "done" ? { color: "var(--accent-D)" } : undefined}
        >
          {syncLabel}
        </button>
        <button type="button" className="btn-accent" onClick={handleExport}>
          내보내기 ↓
        </button>
      </div>
    </div>
  );
}
