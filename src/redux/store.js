// src/redux/store.js
import { configureStore } from '@reduxjs/toolkit';
import reportsReducer from './reportsSlice';
import testsReducer from './testsSlice';

export const store = configureStore({
  reducer: {
    reports: reportsReducer,
    tests: testsReducer,
  },
});