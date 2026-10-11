import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import type { Lesson } from "../api/client";
import { useDayLessons, useMe, useSetLessonStatus, useStudents } from "../api/queries";
import { BonusChest } from "../components/BonusChest";
import { CampBanner } from "../components/CampBanner";
import { KidHeader } from "../components/KidHeader";
import { StickerPanel } from "../components/StickerPanel";
import { StopList } from "../components/StopList";
import { TrailMap, type TrailStop } from "../components/TrailMap";
import { seasonOf, todayISO } from "../lib/dates";
import { buildDailySpark, sparkSolvedKey } from "../lib/spark";
import { campPrize, lessonSticker } from "../lib/stickers";

function firstName(name: string | null | undefined): string {
  return String(name || "").trim().split(/\s+/)[0] || "there";
}

function readSolved(key: string, answer: string): boolean {
  try {
    return window.sessionStorage.getItem(key) === answer;
  } catch {
    return false;
  }
}

/**
 * My trail: today's lessons as stops on the way to camp. A child sees their
 * own day; a parent can open any child's trail (?student=<id>) to see it too.
 */
export function TrailPage() {
  const today = useMemo(() => todayISO(), []);
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const isChild = me.data?.role === "child";
  const students = useStudents(me.isSuccess && !isChild);

  const requested = Number(params.get("student"));
  const child = isChild
    ? me.data
      ? { id: me.data.student_id ?? null, name: me.data.display_name, grade: me.data.grade ?? null }
      : null
    : (() => {
        const list = students.data ?? [];
        const pick = list.find((s) => s.id === requested) ?? list[0];
        return pick ? { id: pick.id, name: pick.name, grade: pick.grade ?? null } : null;
      })();
  const studentId = child?.id ?? null;

  const day = useDayLessons(studentId, today);
  const setStatus = useSetLessonStatus(studentId, today);
  const [poppedId, setPoppedId] = useState<number | null>(null);

  const lessons: Lesson[] = day.data ?? [];
  const firstOpen = lessons.findIndex((lesson) => lesson.status !== "completed");
  const currentIndex = firstOpen === -1 ? lessons.length : firstOpen;
  const done = lessons.length - lessons.filter((lesson) => lesson.status !== "completed").length;
  const campReached = lessons.length > 0 && done === lessons.length;
  const prize = campPrize(today);
  const name = firstName(child?.name);

  const spark = useMemo(
    () => (studentId === null ? null : buildDailySpark({ id: studentId, grade: child?.grade }, lessons, today)),
    [studentId, child?.grade, lessons, today],
  );
  const solvedKey = studentId === null ? "" : sparkSolvedKey(studentId, today);
  const [bonusSolved, setBonusSolved] = useState(false);
  useEffect(() => {
    if (spark && solvedKey) setBonusSolved(readSolved(solvedKey, spark.answer));
  }, [spark, solvedKey]);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.persona = "kid";
    root.dataset.season = seasonOf(today);
    document.title = `${name}’s trail · Curiculy`;
  }, [name, today]);

  const markSolved = () => {
    setBonusSolved(true);
    try {
      if (spark && solvedKey) window.sessionStorage.setItem(solvedKey, spark.answer);
    } catch {
      /* private mode: solved for this visit only */
    }
  };

  const stops: TrailStop[] = lessons.map((lesson) => ({
    id: lesson.id,
    done: lesson.status === "completed",
    sticker: lessonSticker(lesson),
  }));

  if (me.isError || day.isError) {
    return (
      <main className="trail-page">
        <section className="kid-card" role="alert">
          <h1 className="kid-card-title">We couldn’t load your trail</h1>
          <p className="kid-card-sub">Check the internet, then try again.</p>
          <button type="button" className="kid-btn kid-btn-primary" onClick={() => void day.refetch()}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  const loading = me.isPending || (!isChild && students.isPending) || (studentId !== null && day.isPending);
  if (loading) {
    return (
      <main className="trail-page" aria-busy="true">
        <p className="kid-card-sub">Getting your trail ready…</p>
      </main>
    );
  }

  if (studentId === null) {
    return (
      <main className="trail-page">
        <section className="kid-card">
          <h1 className="kid-card-title">No trail yet</h1>
          <p className="kid-card-sub">Add a child in Settings to see their trail.</p>
          <a className="kid-btn" href="/#/settings/students">
            Open Settings
          </a>
        </section>
      </main>
    );
  }

  const label = lessons.length
    ? `Trail map: ${done} of ${lessons.length} stops done${campReached ? ", camp reached" : ""}.`
    : "Trail map: no stops today, a rest day at camp.";

  return (
    <main className="trail-page">
      <KidHeader
        name={name}
        total={lessons.length}
        done={done}
        backHref={isChild ? "/#/my-work" : `/#/students/${studentId}`}
        backLabel={isChild ? "My day" : "Back to Kids"}
      />

      {!isChild && (students.data?.length ?? 0) > 0 && (
        <section className="preview-bar" aria-label="Choose a child">
          <p>Parent preview. Checking off here counts for {name}.</p>
          <div className="preview-chips">
            {students.data!.map((student) => (
              <button
                key={student.id}
                type="button"
                className={`kid-chip${student.id === studentId ? " is-active" : ""}`}
                aria-pressed={student.id === studentId}
                onClick={() => setParams({ student: String(student.id) })}
              >
                {firstName(student.name)}
              </button>
            ))}
          </div>
        </section>
      )}

      {campReached && <CampBanner prize={prize} />}

      <div className="trail-layout">
        <div className="trail-map-card">
          <TrailMap
            stops={stops}
            currentIndex={currentIndex}
            bonusSolved={bonusSolved}
            initial={name.charAt(0).toUpperCase()}
            poppedId={poppedId}
            label={label}
          />
        </div>
        <div className="trail-side">
          {lessons.length > 0 ? (
            <section className="kid-card" aria-labelledby="stops-title">
              <h2 id="stops-title" className="kid-card-title">
                Today’s stops
              </h2>
              <StopList
                lessons={lessons}
                currentIndex={currentIndex}
                busyId={setStatus.isPending ? (setStatus.variables?.id ?? null) : null}
                onDone={(lesson) => {
                  setPoppedId(lesson.id);
                  setStatus.mutate({ id: lesson.id, status: "completed" });
                }}
                onUndo={(lesson) => setStatus.mutate({ id: lesson.id, status: "assigned" })}
              />
              {setStatus.isError && (
                <p className="stop-error" role="alert">
                  That didn’t save. Try again in a moment.
                </p>
              )}
            </section>
          ) : (
            <section className="kid-card">
              <h2 className="kid-card-title">Rest day</h2>
              <p className="kid-card-sub">There are no lessons on today’s trail. Enjoy camp!</p>
            </section>
          )}
          <StickerPanel lessons={lessons} bonusSolved={bonusSolved} campReached={campReached} prize={prize} />
          {spark && <BonusChest spark={spark} solved={bonusSolved} onSolved={markSolved} />}
        </div>
      </div>
    </main>
  );
}
