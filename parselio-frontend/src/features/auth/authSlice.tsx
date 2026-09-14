import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
}

const initialState: AuthState = { accessToken: null, refreshToken: null };

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    loggedIn: (state, action: PayloadAction<{ access: string; refresh: string }>) => {
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
    },
    tokensRefreshed: (state, action: PayloadAction<{ access: string; refresh: string }>) => {
      state.accessToken = action.payload.access;
      state.refreshToken = action.payload.refresh;
    },
    loggedOut: (state) => {
      state.accessToken = null;
      state.refreshToken = null;
    },
  },
});

export const { loggedIn, tokensRefreshed, loggedOut } = authSlice.actions;
export default authSlice.reducer;
