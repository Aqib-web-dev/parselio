import { fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { RootState } from "../store";
import type { BaseQueryFn, FetchArgs, FetchBaseQueryError } from "@reduxjs/toolkit/query/react";
import { tokensRefreshed, loggedOut } from "../features/auth/authSlice";

export const rawBaseQuery = fetchBaseQuery({
  baseUrl: "http://localhost:8000/api/v1/",
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.accessToken;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return headers;
  },
});

export const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  let result = await rawBaseQuery(args, api, extraOptions);

  if (result.error && result.error.status === 401) {
    const refreshToken = (api.getState() as RootState).auth.refreshToken;
    const refreshResult = await rawBaseQuery(
      { url: "token/refresh/", method: "POST", body: { refresh: refreshToken } },
      api,
      extraOptions
    );

    if (refreshResult.data) {
      api.dispatch(tokensRefreshed(refreshResult.data as { access: string; refresh: string }));
      result = await rawBaseQuery(args, api, extraOptions); // retry original request once
    } else {
      api.dispatch(loggedOut());
    }
  }

  return result;
};
