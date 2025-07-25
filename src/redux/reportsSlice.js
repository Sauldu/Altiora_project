// src/redux/reportsSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';

/**
 * @file Slice Redux pour la gestion des rapports.
 * @module redux/reportsSlice
 */

/**
 * Action asynchrone `fetchReports`.
 * 
 * Récupère la liste des rapports depuis l'API.
 * 
 * @returns {Promise<Array<object>>} Une promesse qui résout avec un tableau d'objets rapport.
 */
export const fetchReports = createAsyncThunk(
  'reports/fetchReports',
  async () => {
    const response = await axios.get('http://localhost:8000/reports'); // Assurez-vous que l'URL de l'API est correcte.
    return response.data;
  }
);

/**
 * Slice Redux pour les rapports.
 * 
 * Gère l'état lié aux rapports, y compris le chargement et le stockage des données.
 * 
 * @type {import('@reduxjs/toolkit').Slice}
 */
const reportsSlice = createSlice({
  name: 'reports',
  initialState: {
    reports: [],
    status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
    error: null
  },
  reducers: {
    // Vous pouvez ajouter des reducers synchrones ici si nécessaire.
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchReports.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchReports.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.reports = action.payload; // Met à jour le tableau des rapports avec les données récupérées.
      })
      .addCase(fetchReports.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message; // Stocke le message d'erreur.
      });
  },
});

export default reportsSlice.reducer;
