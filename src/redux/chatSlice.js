// src/redux/chatSlice.js
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async ({ message, file }) => {
    const formData = new FormData();
    formData.append('message', message);
    if (file) formData.append('file', file);

    const response = await fetch('/api/chat', {
      method: 'POST',
      body: formData
    });
    return response.json();
  }
);