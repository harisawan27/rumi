"use client";

import { useEffect, useState } from "react";
import RumiCompanion from "./RumiCompanion";
import type { CompanionMood } from "@/services/companion";
import type { PetActivity } from "@/services/nativeDesktop";
import styles from "./pet.module.css";

const idle: PetActivity = { phase: "idle", message: "", action: null, version: 0, level: 0, visible: false };
const moods: Record<PetActivity["phase"], CompanionMood> = {
  idle: "idle", listening: "listening", speaking: "speaking", working: "thinking",
  permission: "confirming", done: "success", dispatched: "acknowledging", attention: "confused", paused: "stopped",
};

export default function DesktopPet() {
  const [activity, setActivity] = useState<PetActivity>(idle);

  useEffect(() => {
    let gone = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      let delay = 650;
      try {
        const state = await window.pywebview?.api.pet_status?.();
        if (state && !gone) {
          setActivity(state);
          if (state.visible) delay = 180;
        }
      } catch {
        if (!gone) setActivity(idle);
      } finally {
        if (!gone) timer = setTimeout(refresh, delay);
      }
    }
    void refresh();
    return () => { gone = true; clearTimeout(timer); };
  }, []);

  const act = (action: "show" | "word" | "stop") => {
    void window.pywebview?.api.pet_action?.(action).catch(() => {});
  };
  const mood = activity.phase === "working" && activity.message.includes("Word") ? "launching" : moods[activity.phase];
  const label = activity.action === "review" ? "Review" : activity.action === "word" ? "Open in Word" : "Open Rumi";
  return <main className={styles.pet} data-phase={activity.phase} aria-label="Rumi desktop pet">
    <div className={styles.drag} title="Drag Rumi" onPointerDown={event => {
      if (event.button === 0) void window.pywebview?.api.pet_drag?.().catch(() => {});
    }}>
      <RumiCompanion mood={mood} level={activity.level} reaction={activity.version} paused={!activity.visible} preview />
    </div>
    <div className={styles.details}>
      <p className={styles.message} role="status">{activity.message || "Rumi"}</p>
      <div className={styles.controls}>
        <button onClick={() => act(activity.action === "word" ? "word" : "show")}>{label}</button>
        <button className={styles.stop} aria-label="Stop Rumi" title="Stop Rumi" onClick={() => act("stop")}><span aria-hidden="true">■</span></button>
      </div>
    </div>
  </main>;
}
