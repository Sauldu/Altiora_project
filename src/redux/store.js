// src/redux/store.js
import { configureStore } from '@reduxjs/toolkit';
import reportsReducer from './reportsSlice';
import testsReducer from './testsSlice';
import chatReducer from './chatSlice'; // Importe le reducer du chat.

/**
 * @file Configuration du store Redux de l'application Altiora.
 * @module redux/store
 */

/**
 * Configure et crée le store Redux.
 * 
 * Le store est le conteneur de l'état global de l'application.
 * Il combine les différents reducers (slices) pour gérer les différentes
 * parties de l'état.
 * 
 * @type {import('@reduxjs/toolkit').EnhancedStore}
 */
export const store = configureStore({
  reducer: {
    reports: reportsReducer, // Gère l'état lié aux rapports.
    tests: testsReducer,     // Gère l'état lié aux tests.
    chat: chatReducer,       // Gère l'état lié au chat.
  },
  // Vous pouvez ajouter d'autres configurations ici, comme des middlewares,
  // des enhancers, ou des options de développement.
  // middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(myCustomMiddleware),
  // devTools: process.env.NODE_ENV !== 'production',
});

export default store;
