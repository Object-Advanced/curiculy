import type { Student } from "../api/client";
import { firstName } from "../api/kid";

/** A parent previewing kid pages switches children here. */
export function ChildPicker({ students, currentId, name, onPick }: { students: Student[]; currentId: number; name: string; onPick: (id: number) => void }) {
  return (
    <section className="preview-bar" aria-label="Choose a child">
      <p>Parent preview. Checking off here counts for {name}.</p>
      <div className="preview-chips">
        {students.map((student) => (
          <button
            key={student.id}
            type="button"
            className={`kid-chip${student.id === currentId ? " is-active" : ""}`}
            aria-pressed={student.id === currentId}
            onClick={() => onPick(student.id)}
          >
            {firstName(student.name)}
          </button>
        ))}
      </div>
    </section>
  );
}
