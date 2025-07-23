// src/redux/reportsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

export const fetchReports = createAsyncThunk(
  'reports/fetchReports',
  async () => {
    const response = await axios.get('http://localhost:8000/reports');
    return response.data;
  }
);

const reportsSlice = createSlice({
  name: 'reports',
  initialState: { reports: [] },
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(fetchReports.fulfilled, (state, action) => {
      state.reports = action.payload;
    });
  },
});

export default reportsSlice.reducer;