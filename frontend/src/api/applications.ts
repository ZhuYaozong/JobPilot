import { apiClient } from "./client";
import type { ListParams } from "@/types/common";
import type {
  ApplicationEvent,
  ApplicationTransitionRequest,
} from "@/types/application_event";
import type {
  ApplicationRecord,
  ApplicationRecordCreate,
  ApplicationRecordListItem,
  ApplicationRecordUpdate,
} from "@/types/application_record";

export async function listApplications(params: ListParams = {}) {
  const response = await apiClient.get<ApplicationRecordListItem[]>(
    "/api/v1/applications",
    { params },
  );
  return response.data;
}

export async function getApplication(applicationId: number) {
  const response = await apiClient.get<ApplicationRecord>(
    `/api/v1/applications/${applicationId}`,
  );
  return response.data;
}

export async function createApplication(payload: ApplicationRecordCreate) {
  const response = await apiClient.post<ApplicationRecord>(
    "/api/v1/applications",
    payload,
  );
  return response.data;
}

export async function updateApplication(
  applicationId: number,
  payload: ApplicationRecordUpdate,
) {
  const response = await apiClient.patch<ApplicationRecord>(
    `/api/v1/applications/${applicationId}`,
    payload,
  );
  return response.data;
}

export async function deleteApplication(applicationId: number) {
  await apiClient.delete(`/api/v1/applications/${applicationId}`);
}

export async function transitionApplication(
  applicationId: number,
  payload: ApplicationTransitionRequest,
) {
  const response = await apiClient.post<ApplicationRecord>(
    `/api/v1/applications/${applicationId}/transition`,
    payload,
  );
  return response.data;
}

export async function listApplicationEvents(
  applicationId: number,
  params: ListParams = {},
) {
  const response = await apiClient.get<ApplicationEvent[]>(
    `/api/v1/applications/${applicationId}/events`,
    { params },
  );
  return response.data;
}
