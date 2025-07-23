// src/redux/testsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

export const fetchTests = createAsyncThunk(
  'tests/fetchTests',
  async () => {
    const response = await axios.post('http://localhost:8000/tests');
    return response.data;
  }
);

const testsSlice = createSlice({
  name: 'tests',
  initialState: { tests: [] },
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(fetchTests.fulfilled, (state, action) => {
      state.tests = action.payload;
    });
  },
});

export default testsSlice.reducer;