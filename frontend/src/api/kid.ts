import { useSearchParams } from "react-router";

import { useMe, useStudents } from "./queries";

export interface KidChild {
  id: number;
  name: string;
  grade: string | null;
}

export function firstName(name: string | null | undefined): string {
  return String(name || "").trim().split(/\s+/)[0] || "there";
}

/**
 * Whose kid pages these are. A child sees their own; a parent picks a child
 * (`?student=<id>`, else the first) and previews their pages.
 */
export function useKid() {
  const [params, setParams] = useSearchParams();
  const me = useMe();
  const isChild = me.data?.role === "child";
  const students = useStudents(me.isSuccess && !isChild);

  let child: KidChild | null = null;
  if (isChild && me.data) {
    child = me.data.student_id == null ? null : { id: me.data.student_id, name: me.data.display_name, grade: me.data.grade ?? null };
  } else if (!isChild) {
    const list = students.data ?? [];
    const requested = Number(params.get("student"));
    const pick = list.find((student) => student.id === requested) ?? list[0];
    child = pick ? { id: pick.id, name: pick.name, grade: pick.grade ?? null } : null;
  }

  const selectStudent = (id: number) => {
    const next = new URLSearchParams(params);
    next.set("student", String(id));
    setParams(next);
  };

  return {
    me,
    isChild,
    students,
    child,
    studentId: child?.id ?? null,
    name: firstName(child?.name),
    loading: me.isPending || (!isChild && students.isPending),
    error: me.isError || students.isError,
    /** Keeps a parent's chosen child when moving between kid pages. */
    search: !isChild && child ? `?student=${child.id}` : "",
    backHref: isChild ? "/#/my-work" : `/#/students/${child?.id ?? ""}`,
    backLabel: isChild ? "My day" : "Back to Kids",
    selectStudent,
  };
}
