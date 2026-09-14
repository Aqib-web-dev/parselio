import type { useGetUploadUrlMutation, useConfirmUploadMutation } from "@/api/apiSlice";

type GetUploadUrlTrigger = ReturnType<typeof useGetUploadUrlMutation>[0];
type ConfirmUploadTrigger = ReturnType<typeof useConfirmUploadMutation>[0];

export async function uploadDocument(
  file: File,
  meta: { visibility: "company" | "team"; team?: string | null },
  api: { getUploadUrl: GetUploadUrlTrigger; confirmUpload: ConfirmUploadTrigger }
) {
  const { upload_url, document } = await api
    .getUploadUrl({
      title: file.name,
      original_filename: file.name,
      file_size: file.size,
      content_type: file.type,
      ...meta,
    })
    .unwrap();

  await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });

  return api.confirmUpload(document.id).unwrap(); // { status: "uploaded" }
}
