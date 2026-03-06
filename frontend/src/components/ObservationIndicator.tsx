"use client";

export type ObservationState = "active" | "paused" | "degraded";

interface Props {
  state: ObservationState;
}

const CONFIG: Record<ObservationState, { dot: string; label: string }> = {
  active: { dot: "bg-green-500", label: "Observing" },
  paused: { dot: "bg-gray-400", label: "Paused" },
  degraded: { dot: "bg-red-500", label: "Camera unavailable" },
};

export default function ObservationIndicator({ state }: Props) {
  const { dot, label } = CONFIG[state];
  return (
    <div className="flex items-center gap-2 text-sm text-gray-300">
      <span className={`w-2.5 h-2.5 rounded-full ${dot}`} />
      <span>{label}</span>
    </div>
  );
}
