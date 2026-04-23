export type ISODateString = string;

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type JsonObject = { [key: string]: JsonValue };

export interface ListParams {
  limit?: number;
  offset?: number;
}

export interface ApiErrorShape {
  detail?: string;
}
