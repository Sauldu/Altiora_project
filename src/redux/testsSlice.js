// src/redux/testsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

/**
 * @file Slice Redux pour la gestion des tests.
 * @module redux/testsSlice
 */

/**
 * Action asynchrone `fetchTests`.
 * 
 * Récupère la liste des tests depuis l'API.
 * 
 * @returns {Promise<Array<object>>} Une promesse qui résout avec un tableau d'objets test.
 */
export const fetchTests = createAsyncThunk(
  'tests/fetchTests',
  async () => {
    const response = await axios.get('http://localhost:8000/tests'); // Assurez-vous que l'URL de l'API est correcte.
    return response.data;
  }
);

/**
 * Slice Redux pour les tests.
 * 
 * Gère l'état lié aux tests, y compris le chargement et le stockage des données.
 * 
 * @type {import('@reduxjs/toolkit').Slice}
 */
const testsSlice = createSlice({
  name: 'tests',
  initialState: {
    tests: [],
    status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
    error: null
  },
  reducers: {
    // Vous pouvez ajouter des reducers synchrones ici si nécessaire.
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTests.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchTests.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.tests = action.payload; // Met à jour le tableau des tests avec les données récupérées.
      })
      .addCase(fetchTests.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message; // Stocke le message d'erreur.
      });
  },
});

export default testsSlice.reducer;
