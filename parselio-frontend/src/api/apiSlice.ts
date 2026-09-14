import { createApi } from "@reduxjs/toolkit/query/react";
import { baseQueryWithReauth } from "./baseQuery";

export const apiSlice = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  tagTypes: ["Document"],
  endpoints: (builder) => ({
    login: builder.mutation<
      { access: string; refresh: string },
      { username: string; password: string }
    >({
      query: (credentials) => ({
        url: "token/",
        method: "POST",
        body: credentials,
      }),
    }),
    getUploadUrl: builder.mutation<
      { upload_url: string; document: { id: string; status: string } },
      {
        title: string;
        original_filename: string;
        file_size: number;
        content_type: string;
        visibility: "company" | "team";
        team?: string | null;
      }
    >({
      query: (body) => ({ url: "documents/upload-url/", method: "POST", body }),
    }),

    confirmUpload: builder.mutation<{ status: string }, string>({
      query: (documentId) => ({ url: `documents/${documentId}/confirm-upload/`, method: "POST" }),
      invalidatesTags: ["Document"],
    }),

    listDocuments: builder.query<
      {
        results: Array<{ id: string; title: string; status: string; chunk_count: number }>;
        next: string | null;
      },
      void
    >({
      query: () => "documents/",
      providesTags: ["Document"],
    }),
  }),
});

export const {
  useLoginMutation,
  useGetUploadUrlMutation,
  useConfirmUploadMutation,
  useListDocumentsQuery,
} = apiSlice;
