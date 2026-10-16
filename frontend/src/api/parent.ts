/**
 * Parent screens' data: the Library, the Curriculum planner, the community
 * catalog, and the admin review queue. Every call goes through the typed
 * client, so a server change that breaks a screen fails the type check.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, toApiError } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Reference = Schemas["ReferenceRead"];
export type ChoiceOption = Schemas["ChoiceOption"];
export type LibraryItem = Schemas["LibraryItemRead"];
export type LibrarySummary = Schemas["LibraryItemSummary"];
export type LibraryFields = Schemas["LibraryItemUpdate"];
export type LibraryCreate = Schemas["LibraryItemCreate"];
export type ChapterWrite = Schemas["ChapterWrite"];
export type LessonWrite = Schemas["LessonWrite"];
export type SearchResult = Schemas["SearchResult"];
export type SearchResults = Schemas["SearchResults"];
export type Readiness = Schemas["ReadinessRead"];
export type CommunityEntry = Schemas["CommunityEntryRead"];
export type CommunitySummary = Schemas["CommunityEntrySummary"];
export type Suggestions = Schemas["SuggestionsRead"];
export type SuggestedItem = Schemas["SuggestedItem"];
export type Curriculum = Schemas["PlannedCurriculumRead"];
export type CurriculumItem = Schemas["CurriculumItemRead"];
export type SchedulePreview = Schemas["SchedulePreview"];
export type ScheduleResult = Schemas["ScheduleResult"];
export type ScheduleRequest = Schemas["ScheduleRequest"];
export type ContributionSummary = Schemas["ContributionSummary"];
export type ContributionDetail = Schemas["ContributionDetail"];
export type EntryAdmin = Schemas["EntryAdminRead"];
export type ApproveRequest = Schemas["ApproveRequest"];
export type Pace = Schemas["PaceRead"];
export type Course = Schemas["CourseRead"];
export type BarcodeReading = Schemas["BarcodeRead"];
export type PageReading = Schemas["PageReadingRead"];
export type ReadingEntry = Schemas["ReadingEntryRead"];
export type ReadingCreate = Schemas["ReadingEntryCreate"];
export type ReadingUpdate = Schemas["ReadingEntryUpdate"];
export type Activity = Schemas["ActivityRead"];
export type ActivityCreate = Schemas["ActivityCreate"];
export type ActivityUpdate = Schemas["ActivityUpdate"];
export type AttendanceDays = Schemas["AttendanceDays"];
export type AttendanceDay = Schemas["AttendanceDayCard"];
export type AttendanceChild = Schemas["AttendanceChildDay"];
export type AttendanceMark = Schemas["AttendanceMark"];
export type AttendanceSummary = Schemas["AttendanceSummary"];
export type AttendanceStatus = Schemas["AttendanceStatus"];

export const parentKeys = {
  reference: ["reference"] as const,
  library: ["library"] as const,
  item: (id: number) => ["library", "item", id] as const,
  search: (q: string) => ["library", "search", q] as const,
  entry: (id: number) => ["community", "entry", id] as const,
  suggestions: (itemId: number) => ["community", "suggestions", itemId] as const,
  curricula: ["planner"] as const,
  curriculum: (id: number) => ["planner", id] as const,
  queue: (status: string) => ["admin", "queue", status] as const,
  contribution: (id: number) => ["admin", "contribution", id] as const,
  entries: (q: string) => ["admin", "entries", q] as const,
  entryAdmin: (id: number) => ["admin", "entry", id] as const,
  reading: ["reading"] as const,
  readingFor: (studentId: number) => ["reading", "student", studentId] as const,
  readersOf: (itemId: number) => ["reading", "item", itemId] as const,
  activities: ["activities"] as const,
  attendance: ["attendance"] as const,
  attendanceDays: (from: string, to: string) => ["attendance", "days", from, to] as const,
  attendanceSummary: ["attendance", "summary"] as const,
};

/** Unwrap an openapi-fetch result, or throw the server's message. */
function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined && result.response.status !== 204) {
    throw toApiError(result.response, result.error);
  }
  return result.data as T;
}

// ---- Reference ---------------------------------------------------------------

export function useReference() {
  return useQuery({
    queryKey: parentKeys.reference,
    queryFn: async () => unwrap(await api.GET("/api/reference")),
    staleTime: Infinity,
  });
}

// ---- Library -----------------------------------------------------------------

export function useLibrary() {
  return useQuery({
    queryKey: parentKeys.library,
    queryFn: async () => unwrap(await api.GET("/api/library")),
  });
}

export function useLibraryItem(id: number | null) {
  return useQuery({
    queryKey: parentKeys.item(id ?? 0),
    queryFn: async () => unwrap(await api.GET("/api/library/{item_id}", { params: { path: { item_id: id as number } } })),
    enabled: id !== null,
  });
}

export async function searchLibrary(q: string): Promise<SearchResults> {
  return unwrap(await api.GET("/api/library/search", { params: { query: { q } } }));
}

/** After any change to an item: refresh it, the shelf, and the curricula that show it. */
function useItemSaved() {
  const queryClient = useQueryClient();
  return (item: LibraryItem) => {
    queryClient.setQueryData(parentKeys.item(item.id), item);
    // The shelf and the curricula show it too; the item itself is already fresh.
    void queryClient.invalidateQueries({ queryKey: parentKeys.library, exact: true });
    void queryClient.invalidateQueries({ queryKey: parentKeys.curricula });
  };
}

export function useCreateItem() {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (body: LibraryCreate) => unwrap(await api.POST("/api/library", { body })),
    onSuccess: saved,
  });
}

export function useAddFromCommunity() {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (entryId: number) =>
      unwrap(await api.POST("/api/library/from-community", { body: { entry_id: entryId } })),
    onSuccess: saved,
  });
}

export function useUpdateItem(id: number) {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (body: LibraryFields) =>
      unwrap(await api.PATCH("/api/library/{item_id}", { params: { path: { item_id: id } }, body })),
    onSuccess: saved,
  });
}

export function useSaveChapters(id: number) {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (body: ChapterWrite[]) =>
      unwrap(await api.PUT("/api/library/{item_id}/chapters", { params: { path: { item_id: id } }, body })),
    onSuccess: saved,
  });
}

export function useSaveLessons(id: number) {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (body: LessonWrite[]) =>
      unwrap(await api.PUT("/api/library/{item_id}/lessons", { params: { path: { item_id: id } }, body })),
    onSuccess: saved,
  });
}

export function useUploadCover(id: number) {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST("/api/library/{item_id}/cover", {
          params: { path: { item_id: id } },
          body: { file: file as unknown as string },
          bodySerializer: () => {
            const form = new FormData();
            form.append("file", file);
            return form;
          },
        }),
      ),
    onSuccess: saved,
  });
}

export function useRemoveCover(id: number) {
  const saved = useItemSaved();
  return useMutation({
    mutationFn: async () => unwrap(await api.DELETE("/api/library/{item_id}/cover", { params: { path: { item_id: id } } })),
    onSuccess: saved,
  });
}

export function useDeleteItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(await api.DELETE("/api/library/{item_id}", { params: { path: { item_id: id } } }));
      return id;
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: parentKeys.item(id) });
      void queryClient.invalidateQueries({ queryKey: parentKeys.library });
      void queryClient.invalidateQueries({ queryKey: parentKeys.curricula });
    },
  });
}

// ---- Community catalog (families) -------------------------------------------

export function useCommunityEntry(id: number | null) {
  return useQuery({
    queryKey: parentKeys.entry(id ?? 0),
    queryFn: async () =>
      unwrap(await api.GET("/api/community/entries/{entry_id}", { params: { path: { entry_id: id as number } } })),
    enabled: id !== null,
  });
}

export function useSuggestions(libraryItemId: number | null) {
  return useQuery({
    queryKey: parentKeys.suggestions(libraryItemId ?? 0),
    queryFn: async () =>
      unwrap(await api.GET("/api/community/suggestions", { params: { query: { library_item_id: libraryItemId as number } } })),
    enabled: libraryItemId !== null,
  });
}

// ---- Curriculum planner ------------------------------------------------------

export function useCurricula() {
  return useQuery({
    queryKey: parentKeys.curricula,
    queryFn: async () => unwrap(await api.GET("/api/planner/curricula")),
  });
}

export function useCurriculum(id: number | null) {
  return useQuery({
    queryKey: parentKeys.curriculum(id ?? 0),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/planner/curricula/{planned_curriculum_id}", {
          params: { path: { planned_curriculum_id: id as number } },
        }),
      ),
    enabled: id !== null,
  });
}

function useCurriculumSaved() {
  const queryClient = useQueryClient();
  return (curriculum: Curriculum) => {
    queryClient.setQueryData(parentKeys.curriculum(curriculum.id), curriculum);
    void queryClient.invalidateQueries({ queryKey: parentKeys.curricula, exact: true });
    void queryClient.invalidateQueries({ queryKey: parentKeys.library });
  };
}

export function useCreateCurriculum() {
  const saved = useCurriculumSaved();
  return useMutation({
    mutationFn: async (body: Schemas["PlannedCurriculumCreate"]) => unwrap(await api.POST("/api/planner/curricula", { body })),
    onSuccess: saved,
  });
}

export function useCurriculumFromCommunity() {
  const saved = useCurriculumSaved();
  return useMutation({
    mutationFn: async (body: Schemas["FromCommunityRequest"]) =>
      unwrap(await api.POST("/api/planner/curricula/from-community", { body })),
    onSuccess: saved,
  });
}

export function useUpdateCurriculum(id: number) {
  const saved = useCurriculumSaved();
  return useMutation({
    mutationFn: async (body: Schemas["PlannedCurriculumUpdate"]) =>
      unwrap(
        await api.PATCH("/api/planner/curricula/{planned_curriculum_id}", {
          params: { path: { planned_curriculum_id: id } },
          body,
        }),
      ),
    onSuccess: saved,
  });
}

export function useAddCurriculumItem(id: number) {
  const saved = useCurriculumSaved();
  return useMutation({
    mutationFn: async (body: Schemas["CurriculumItemWrite"]) =>
      unwrap(
        await api.POST("/api/planner/curricula/{planned_curriculum_id}/items", {
          params: { path: { planned_curriculum_id: id } },
          body,
        }),
      ),
    onSuccess: saved,
  });
}

export function useRemoveCurriculumItem(id: number) {
  const saved = useCurriculumSaved();
  return useMutation({
    mutationFn: async (libraryItemId: number) =>
      unwrap(
        await api.DELETE("/api/planner/curricula/{planned_curriculum_id}/items/{item_id}", {
          params: { path: { planned_curriculum_id: id, item_id: libraryItemId } },
        }),
      ),
    onSuccess: saved,
  });
}

export function useDeleteCurriculum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      unwrap(
        await api.DELETE("/api/planner/curricula/{planned_curriculum_id}", {
          params: { path: { planned_curriculum_id: id } },
        }),
      );
      return id;
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: parentKeys.curriculum(id) });
      void queryClient.invalidateQueries({ queryKey: parentKeys.curricula });
      void queryClient.invalidateQueries({ queryKey: parentKeys.library });
    },
  });
}

export async function previewSchedule(id: number, body: ScheduleRequest): Promise<SchedulePreview> {
  return unwrap(
    await api.POST("/api/planner/curricula/{planned_curriculum_id}/schedule/preview", {
      params: { path: { planned_curriculum_id: id } },
      body,
    }),
  );
}

export function useSchedule(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScheduleRequest) =>
      unwrap(
        await api.POST("/api/planner/curricula/{planned_curriculum_id}/schedule", {
          params: { path: { planned_curriculum_id: id } },
          body,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: parentKeys.curricula });
      // Its books to read go on the children's reading lists.
      void queryClient.invalidateQueries({ queryKey: parentKeys.reading });
    },
  });
}

export function useUnschedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (courseId: number) =>
      unwrap(await api.DELETE("/api/planner/courses/{course_id}", { params: { path: { course_id: courseId } } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: parentKeys.curricula });
      // A book scheduled on its own shows its courses in the Library.
      void queryClient.invalidateQueries({ queryKey: parentKeys.library });
      void queryClient.invalidateQueries({ queryKey: parentKeys.reading });
    },
  });
}

// ---- One book on its own (the Library's "Schedule") ---------------------------

export async function previewItemSchedule(itemId: number, body: ScheduleRequest): Promise<SchedulePreview> {
  return unwrap(
    await api.POST("/api/library/{item_id}/schedule/preview", { params: { path: { item_id: itemId } }, body }),
  );
}

export function useScheduleItem(itemId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScheduleRequest) =>
      unwrap(await api.POST("/api/library/{item_id}/schedule", { params: { path: { item_id: itemId } }, body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: parentKeys.library });
      // A book scheduled on its own goes on the child's reading list.
      void queryClient.invalidateQueries({ queryKey: parentKeys.reading });
    },
  });
}

// ---- Reading photos -------------------------------------------------------------

function photoBody(file: File) {
  return {
    body: { file: file as unknown as string },
    bodySerializer: () => {
      const form = new FormData();
      form.append("file", file);
      return form;
    },
  };
}

/** The ISBN from a photo of a book's barcode. */
export async function readBarcodePhoto(file: File): Promise<BarcodeReading> {
  return unwrap(await api.POST("/api/library/read-barcode", photoBody(file)));
}

/** Chapters or lessons, one per line, from a photo of a printed page. */
export async function readPagePhoto(file: File): Promise<PageReading> {
  return unwrap(await api.POST("/api/library/read-page", photoBody(file)));
}

// ---- Admin review queue ------------------------------------------------------

export function useQueue(status: string) {
  return useQuery({
    queryKey: parentKeys.queue(status),
    queryFn: async () =>
      unwrap(await api.GET("/api/admin/community/contributions", { params: { query: { status } } })),
  });
}

export function useContribution(id: number | null) {
  return useQuery({
    queryKey: parentKeys.contribution(id ?? 0),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/admin/community/contributions/{contribution_id}", {
          params: { path: { contribution_id: id as number } },
        }),
      ),
    enabled: id !== null,
  });
}

type ReviewAction =
  | { action: "approve"; body: ApproveRequest }
  | { action: "merge"; body: Schemas["MergeRequest"] }
  | { action: "reject"; body: Schemas["RejectRequest"] }
  | { action: "ask"; body: Schemas["AskRequest"] };

export function useReview(contributionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (review: ReviewAction) => {
      const params = { path: { contribution_id: contributionId } };
      switch (review.action) {
        case "approve":
          return unwrap(await api.POST("/api/admin/community/contributions/{contribution_id}/approve", { params, body: review.body }));
        case "merge":
          return unwrap(await api.POST("/api/admin/community/contributions/{contribution_id}/merge", { params, body: review.body }));
        case "reject":
          return unwrap(await api.POST("/api/admin/community/contributions/{contribution_id}/reject", { params, body: review.body }));
        case "ask":
          return unwrap(await api.POST("/api/admin/community/contributions/{contribution_id}/ask", { params, body: review.body }));
      }
    },
    onSuccess: (result) => {
      queryClient.setQueryData(parentKeys.contribution(contributionId), result.contribution);
      void queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}

export function useCatalogEntries(q: string) {
  return useQuery({
    queryKey: parentKeys.entries(q),
    queryFn: async () => unwrap(await api.GET("/api/admin/community/entries", { params: { query: q ? { q } : {} } })),
  });
}

export function useEntryAdmin(id: number | null) {
  return useQuery({
    queryKey: parentKeys.entryAdmin(id ?? 0),
    queryFn: async () =>
      unwrap(await api.GET("/api/admin/community/entries/{entry_id}", { params: { path: { entry_id: id as number } } })),
    enabled: id !== null,
  });
}

export function useEntryAction(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (change: { action: "rollback"; version: number } | { action: "retire" | "publish" }) => {
      const params = { path: { entry_id: id } };
      if (change.action === "rollback") {
        return unwrap(
          await api.POST("/api/admin/community/entries/{entry_id}/rollback", { params, body: { version: change.version } }),
        );
      }
      if (change.action === "retire") return unwrap(await api.POST("/api/admin/community/entries/{entry_id}/retire", { params }));
      return unwrap(await api.POST("/api/admin/community/entries/{entry_id}/publish", { params }));
    },
    onSuccess: (entry) => {
      queryClient.setQueryData(parentKeys.entryAdmin(id), entry);
      void queryClient.invalidateQueries({ queryKey: ["admin", "entries"] });
    },
  });
}

// ---- Reading lists ------------------------------------------------------------------

/** One child's reading list: reading now, up next, then finished (most recent first). */
export function useReadingList(studentId: number | null) {
  return useQuery({
    queryKey: parentKeys.readingFor(studentId ?? 0),
    queryFn: async () =>
      unwrap(await api.GET("/api/reading-list", { params: { query: { student_id: studentId as number } } })),
    enabled: studentId !== null,
  });
}

/** Who has a book on their list (the Library item panel). */
export function useReadersOf(itemId: number | null) {
  return useQuery({
    queryKey: parentKeys.readersOf(itemId ?? 0),
    queryFn: async () =>
      unwrap(await api.GET("/api/reading-list", { params: { query: { library_item_id: itemId as number } } })),
    enabled: itemId !== null,
  });
}

function useReadingChanged() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: parentKeys.reading });
}

export function useAddReading() {
  const changed = useReadingChanged();
  return useMutation({
    mutationFn: async (body: ReadingCreate) => unwrap(await api.POST("/api/reading-list", { body })),
    onSuccess: changed,
  });
}

export function useUpdateReading() {
  const changed = useReadingChanged();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ReadingUpdate }) =>
      unwrap(await api.PATCH("/api/reading-list/{reading_id}", { params: { path: { reading_id: id } }, body })),
    onSuccess: changed,
  });
}

export function useRemoveReading() {
  const changed = useReadingChanged();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.DELETE("/api/reading-list/{reading_id}", { params: { path: { reading_id: id } } })),
    onSuccess: changed,
  });
}

// ---- Activities ---------------------------------------------------------------------

/** Every activity, newest first; the page filters by child. */
export function useActivities() {
  return useQuery({
    queryKey: parentKeys.activities,
    queryFn: async () => unwrap(await api.GET("/api/activities")),
  });
}

export async function createActivity(body: ActivityCreate): Promise<Activity> {
  return unwrap(await api.POST("/api/activities", { body }));
}

export async function updateActivity(id: number, body: ActivityUpdate): Promise<Activity> {
  return unwrap(await api.PATCH("/api/activities/{activity_id}", { params: { path: { activity_id: id } }, body }));
}

export async function addActivityPhoto(id: number, file: File) {
  return unwrap(
    await api.POST("/api/activities/{activity_id}/evidence", {
      params: { path: { activity_id: id } },
      ...photoBody(file),
    }),
  );
}

export async function removeActivityPhoto(id: number, evidenceId: number) {
  return unwrap(
    await api.DELETE("/api/activities/{activity_id}/evidence/{activity_evidence_id}", {
      params: { path: { activity_id: id, activity_evidence_id: evidenceId } },
    }),
  );
}

export function useDeleteActivity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.DELETE("/api/activities/{activity_id}", { params: { path: { activity_id: id } } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: parentKeys.activities }),
  });
}

// ---- Attendance ---------------------------------------------------------------------

/** Each day and child: what's marked and what the day's work suggests. No dates: the family's today. */
export function useAttendanceDays(from?: string, to?: string, enabled = true) {
  return useQuery({
    queryKey: parentKeys.attendanceDays(from ?? "today", to ?? from ?? "today"),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/attendance/days", {
          params: { query: { ...(from ? { start_date: from } : {}), ...(to ? { end_date: to } : {}) } },
        }),
      ),
    enabled,
  });
}

export function useAttendanceSummary() {
  return useQuery({
    queryKey: parentKeys.attendanceSummary,
    queryFn: async () => unwrap(await api.GET("/api/attendance/summary")),
  });
}

/** "Looks right": save the parent's marks, then refresh every day card and the counts. */
export function useConfirmAttendance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (marks: AttendanceMark[]) =>
      unwrap(await api.POST("/api/attendance/confirm", { body: { marks } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: parentKeys.attendance }),
  });
}
