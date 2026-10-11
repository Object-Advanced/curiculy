import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError, type Lesson, type LessonStatus, type Me, type Student } from "./client";

export const keys = {
  me: ["me"] as const,
  students: ["students"] as const,
  day: (studentId: number, iso: string) => ["day", studentId, iso] as const,
  range: (studentId: number, from: string, to: string) => ["range", studentId, from, to] as const,
};

async function fetchMe(): Promise<Me> {
  const { data, error, response } = await api.GET("/api/auth/me");
  if (!data) throw toApiError(response, error);
  return data;
}

async function fetchStudents(): Promise<Student[]> {
  const { data, error, response } = await api.GET("/api/students");
  if (!data) throw toApiError(response, error);
  return data;
}

async function fetchDay(studentId: number, iso: string): Promise<Lesson[]> {
  const { data, error, response } = await api.GET("/api/students/{student_id}/assignments", {
    params: { path: { student_id: studentId }, query: { start_date: iso, end_date: iso } },
  });
  if (!data) throw toApiError(response, error);
  // Stops follow the order lessons were planned in.
  return [...data.assignments].sort((a, b) => a.id - b.id);
}

async function fetchRange(studentId: number, from: string, to: string): Promise<Lesson[]> {
  const { data, error, response } = await api.GET("/api/students/{student_id}/assignments", {
    params: { path: { student_id: studentId }, query: { start_date: from, end_date: to } },
  });
  if (!data) throw toApiError(response, error);
  return data.assignments;
}

/** Every lesson scheduled between two dates (inclusive), for the Sticker journal. */
export function useLessonsBetween(studentId: number | null, from: string, to: string) {
  return useQuery({
    queryKey: keys.range(studentId ?? 0, from, to),
    queryFn: () => fetchRange(studentId as number, from, to),
    enabled: studentId !== null,
  });
}

export function useMe() {
  return useQuery({ queryKey: keys.me, queryFn: fetchMe });
}

/** Parents pick which child's trail to view; children never call this. */
export function useStudents(enabled: boolean) {
  return useQuery({ queryKey: keys.students, queryFn: fetchStudents, enabled });
}

export function useDayLessons(studentId: number | null, iso: string) {
  return useQuery({
    queryKey: keys.day(studentId ?? 0, iso),
    queryFn: () => fetchDay(studentId as number, iso),
    enabled: studentId !== null,
  });
}

/** Check a lesson off (or back on), updating the trail before the server answers. */
export function useSetLessonStatus(studentId: number | null, iso: string) {
  const queryClient = useQueryClient();
  const key = keys.day(studentId ?? 0, iso);
  return useMutation({
    mutationFn: async ({ id, status }: { id: number; status: LessonStatus }) => {
      const { data, error, response } = await api.PATCH("/api/assignments/{assignment_id}/status", {
        params: { path: { assignment_id: id } },
        body: { status },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Lesson[]>(key);
      queryClient.setQueryData<Lesson[]>(key, (lessons) =>
        lessons?.map((lesson) => (lesson.id === id ? { ...lesson, status } : lesson)),
      );
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });
}
