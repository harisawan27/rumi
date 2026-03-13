"use client";

export type ObservationState = "active" | "paused" | "degraded";

interface Props {
  state: ObservationState;
}

const CONFIG: Record<ObservationState, { color: string; label: string }> = {
  active:   { color: "var(--teal)",    label: "Observing" },
  paused:   { color: "var(--muted)",   label: "Paused" },
  degraded: { color: "#f97316",        label: "Camera unavailable" },
};

export default function ObservationIndicator({ state }: Props) {
  const { color, label } = CONFIG[state];
  return (
    <div className="flex items-center gap-2">
      <span
        className="rounded-full"
        style={{
          width: 8, height: 8,
          backgroundColor: color,
          boxShadow: state === "active" ? `0 0 8px ${color}` : "none",
        }}
      />
      <span className="text-sm" style={{ color: "var(--text-2)" }}>{label}</span>
    </div>
  );
}
