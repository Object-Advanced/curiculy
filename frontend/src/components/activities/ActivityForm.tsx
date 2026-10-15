import { useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";

import {
  addActivityPhoto,
  createActivity,
  parentKeys,
  removeActivityPhoto,
  updateActivity,
  useDeleteActivity,
  useReference,
  type Activity,
} from "../../api/parent";
import type { Student } from "../../api/client";
import { todayISO } from "../../lib/dates";
import { ErrorLine, NumberField, TextArea, TextField } from "../ui/Fields";
import { Modal } from "../ui/Modal";
import { ActivityPhoto } from "./ActivityPhoto";

interface Draft {
  title: string;
  on_date: string;
  student_ids: number[];
  subject_codes: string[];
  minutes: number | null;
  link_url: string;
  notes: string;
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

/**
 * Log an activity, or change one: what, when, who, which subjects it counts
 * toward, and photos (work samples) or a link to a video.
 */
export function ActivityForm({
  activity,
  students,
  defaultStudentIds,
  onClose,
}: {
  activity: Activity | null;
  students: Student[];
  defaultStudentIds: number[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const reference = useReference();
  const remove = useDeleteActivity();
  const photosId = useId();
  const [draft, setDraft] = useState<Draft>(() =>
    activity
      ? {
          title: activity.title,
          on_date: activity.on_date,
          student_ids: activity.students.map((child) => child.student_id),
          subject_codes: activity.subjects.map((subject) => subject.code),
          minutes: activity.minutes ?? null,
          link_url: activity.link_url ?? "",
          notes: activity.notes ?? "",
        }
      : {
          title: "",
          on_date: todayISO(),
          student_ids: defaultStudentIds,
          subject_codes: [],
          minutes: null,
          link_url: "",
          notes: "",
        },
  );
  const [files, setFiles] = useState<File[]>([]);
  const [removed, setRemoved] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirming, setConfirming] = useState(false);
  // What already reached the server, so trying again after a failed photo
  // doesn't log the activity twice or upload a photo twice.
  const progress = useRef({ id: activity?.id ?? null, removed: new Set<number>(), uploaded: new Set<File>() });
  const change = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }));
  const photos = (activity?.evidence ?? []).filter((photo) => !removed.includes(photo.id));
  const ready = draft.title.trim() !== "" && draft.on_date !== "" && draft.student_ids.length > 0;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const body = {
        title: draft.title.trim(),
        on_date: draft.on_date,
        student_ids: draft.student_ids,
        subject_codes: draft.subject_codes,
        minutes: draft.minutes,
        link_url: draft.link_url.trim() || null,
        notes: draft.notes.trim() || null,
      };
      const done = progress.current;
      const saved = done.id ? await updateActivity(done.id, body) : await createActivity(body);
      done.id = saved.id;
      for (const id of removed) {
        if (done.removed.has(id)) continue;
        await removeActivityPhoto(saved.id, id);
        done.removed.add(id);
      }
      for (const file of files) {
        if (done.uploaded.has(file)) continue;
        await addActivityPhoto(saved.id, file);
        done.uploaded.add(file);
      }
      await queryClient.invalidateQueries({ queryKey: parentKeys.activities });
      onClose();
    } catch (problem) {
      setError(problem);
      // Whatever did save shows on the list behind the form.
      void queryClient.invalidateQueries({ queryKey: parentKeys.activities });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={activity ? activity.title : "Log an activity"}
      onClose={onClose}
      wide
      footer={
        <>
          {activity ? (
            confirming ? (
              <div className="row">
                <span className="small">Delete this activity and its photos?</span>
                <button
                  type="button"
                  className="btn btn-danger btn-small"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(activity.id, { onSuccess: onClose })}
                >
                  Yes, delete it
                </button>
                <button type="button" className="btn btn-quiet btn-small" onClick={() => setConfirming(false)}>
                  Keep it
                </button>
              </div>
            ) : (
              <button type="button" className="btn btn-danger btn-small" onClick={() => setConfirming(true)}>
                Delete
              </button>
            )
          ) : (
            <button type="button" className="btn btn-quiet" onClick={onClose}>
              Cancel
            </button>
          )}
          <button type="button" className="btn btn-primary" disabled={!ready || saving} onClick={() => void save()}>
            {saving ? "Saving…" : activity ? "Save changes" : "Log it"}
          </button>
        </>
      }
    >
      <div className="stack-lg">
        <div className="form-grid">
          <TextField
            label="What did you do?"
            required
            wide
            autoFocus
            value={draft.title}
            onChange={(value) => change({ title: value })}
            placeholder="5K race, piano recital, fire station visit"
          />
          <TextField label="Date" type="date" required value={draft.on_date} onChange={(value) => change({ on_date: value })} />
          <NumberField
            label="Minutes"
            max={720}
            value={draft.minutes}
            onChange={(value) => change({ minutes: value })}
            hint="Optional. Families who count hours add these up."
          />
        </div>

        <fieldset className="field">
          <legend className="field-label">
            Who took part?
            <span className="field-required" aria-hidden="true">
              {" "}
              *
            </span>
          </legend>
          <div className="chips">
            {students.map((student) => (
              <button
                key={student.id}
                type="button"
                className="chip"
                aria-pressed={draft.student_ids.includes(student.id)}
                onClick={() => change({ student_ids: toggle(draft.student_ids, student.id) })}
              >
                {student.name}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="field">
          <legend className="field-label">Counts toward</legend>
          <p className="field-hint">Pick every subject it covers: a nature walk can be Science and Physical education.</p>
          <div className="chips">
            {(reference.data?.subjects ?? []).map((subject) => (
              <button
                key={subject.code}
                type="button"
                className="chip"
                aria-pressed={draft.subject_codes.includes(subject.code)}
                onClick={() => change({ subject_codes: toggle(draft.subject_codes, subject.code) })}
              >
                {subject.name}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="stack">
          <label className="field-label" htmlFor={photosId}>
            Photos
          </label>
          <p className="field-hint" id={`${photosId}-hint`}>
            Photos or PDFs (a program, a certificate, the finish line). They're work samples in your records.
          </p>
          {photos.length ? (
            <ul className="photo-strip" aria-label="Photos">
              {photos.map((photo) => (
                <li key={photo.id} className="stack">
                  <ActivityPhoto filePath={photo.file_path} label={draft.title} />
                  <button type="button" className="btn btn-quiet btn-small" onClick={() => setRemoved([...removed, photo.id])}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <input
            id={photosId}
            type="file"
            accept="image/*,application/pdf"
            multiple
            aria-describedby={`${photosId}-hint`}
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          />
          {files.length ? (
            <p className="small" role="status">
              {files.length} new file{files.length === 1 ? "" : "s"} to add when you save.
            </p>
          ) : null}
        </div>

        <div className="form-grid">
          <TextField
            label="A link"
            type="url"
            wide
            value={draft.link_url}
            onChange={(value) => change({ link_url: value })}
            placeholder="https://"
            hint="A video of the recital or the game: an unlisted YouTube video or a shared Drive file."
          />
          <TextArea label="Notes" rows={3} value={draft.notes} onChange={(value) => change({ notes: value })} />
        </div>
        <ErrorLine error={error ?? remove.error} />
      </div>
    </Modal>
  );
}
