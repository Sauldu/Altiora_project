// src/redux/chatSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

/**
 * @file Slice Redux pour la gestion des fonctionnalités de chat.
 * @module redux/chatSlice
 */

/**
 * Action asynchrone `sendMessage`.
 * 
 * Envoie un message (et un fichier optionnel) à l'API de chat.
 * Cette action est utilisée pour interagir avec le backend et envoyer les données du chat.
 * 
 * @param {object} payload - L'objet contenant le message et le fichier.
 * @param {string} payload.message - Le contenu du message à envoyer.
 * @param {File} [payload.file] - Le fichier optionnel à joindre au message.
 * @returns {Promise<object>} Une promesse qui résout avec la réponse JSON de l'API.
 */
export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async ({ message, file }) => {
    const formData = new FormData();
    formData.append('message', message);
    if (file) formData.append('file', file);

    const response = await fetch('/api/chat', { // Assurez-vous que l'URL de l'API est correcte.
      method: 'POST',
      body: formData
    });
    // Gérer les erreurs de réponse HTTP si nécessaire.
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.message || 'Échec de l'envoi du message');
    }
    return response.json();
  }
);

/**
 * Slice Redux pour le chat.
 * 
 * Gère l'état lié au chat, y compris les messages envoyés et les réponses reçues.
 * 
 * @type {import('@reduxjs/toolkit').Slice}
 */
const chatSlice = createSlice({
  name: 'chat',
  initialState: {
    messages: [],
    status: 'idle', // 'idle' | 'loading' | 'succeeded' | 'failed'
    error: null
  },
  reducers: {
    // Vous pouvez ajouter des reducers synchrones ici si nécessaire.
    addMessage: (state, action) => {
      state.messages.push(action.payload);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.status = 'succeeded';
        // Ajoute la réponse du serveur aux messages.
        state.messages.push({ type: 'bot', text: action.payload.response });
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message;
        state.messages.push({ type: 'bot', text: `Erreur: ${action.error.message}` });
      });
  },
});

export const { addMessage } = chatSlice.actions;
export default chatSlice.reducer;
