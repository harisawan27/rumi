import type { WindowsTask } from "@/services/nativeDesktop";
import s from "./taskSheet.module.css";

export default function TaskSheet({ task, state }: { task: WindowsTask; state: string }) {
  const choosing = state === "task_choice";
  const approval = state === "plan";
  return <section className={s.sheet} aria-label="Windows task" data-stage={state}>
    <div className={s.target} title={task.window}><span/><span>{task.window}</span></div>
    <h3 title={task.goal}>{task.goal}</h3>
    <ol aria-label={choosing ? "Available controls" : "Task steps"}>
      {task.items.map((item, i) => <li key={`${i}-${item}`}>
        <span aria-hidden="true" className={s.marker}>{choosing || approval ? i + 1 : "✓"}</span>
        <span title={item}>{item}</span>
      </li>)}
    </ol>
    <p className={s.hint}>{choosing ? "Say “Rumi, choose option one” or another number." : approval ? "Say “Rumi, confirm window plan”." : "Say “Rumi, read result page” to hear this again."}</p>
  </section>;
}
