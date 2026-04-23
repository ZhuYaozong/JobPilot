import { apiClient } from "./client";
import type { ListParams } from "@/types/common";
import type {
  MatchAnalysisRequest,
  MatchResult,
  MatchResultCreate,
  MatchResultListItem,
  MatchResultUpdate,
} from "@/types/match_result";

export async function listMatches(params: ListParams = {}) {
  const response = await apiClient.get<MatchResultListItem[]>("/api/v1/matches", {
    params,
  });
  return response.data;
}

export async function getMatch(matchId: number) {
  const response = await apiClient.get<MatchResult>(`/api/v1/matches/${matchId}`);
  return response.data;
}

export async function createMatch(payload: MatchResultCreate) {
  const response = await apiClient.post<MatchResult>("/api/v1/matches", payload);
  return response.data;
}

export async function updateMatch(matchId: number, payload: MatchResultUpdate) {
  const response = await apiClient.patch<MatchResult>(
    `/api/v1/matches/${matchId}`,
    payload,
  );
  return response.data;
}

export async function analyzeMatch(payload: MatchAnalysisRequest) {
  const response = await apiClient.post<MatchResult>(
    "/api/v1/matches/analyze",
    payload,
  );
  return response.data;
}
