// src/components/Tests.js
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchTests } from '../redux/testsSlice';
import { DataGrid } from '@mui/x-data-grid';

/**
 * @file Composant d'affichage des tests pour l'application Altiora.
 * @module components/Tests
 */

/**
 * Composant `Tests`.
 * 
 * Ce composant React affiche une liste de tests dans une grille de données.
 * Il utilise Redux pour gérer l'état des tests et Material-UI DataGrid pour l'affichage.
 * Les tests sont récupérés au montage du composant via l'action `fetchTests`.
 * 
 * @returns {JSX.Element} Le composant d'affichage des tests.
 */
const Tests = () => {
  // Hook pour dispatcher des actions Redux.
  const dispatch = useDispatch();
  // Hook pour sélectionner des données depuis le store Redux.
  const tests = useSelector(state => state.tests.tests);

  // Effet de bord pour récupérer les tests au montage du composant.
  useEffect(() => {
    /**
     * Dispatch l'action `fetchTests` pour charger les données des tests.
     * Cette action est exécutée une seule fois au montage du composant.
     */
    dispatch(fetchTests());
  }, [dispatch]); // `dispatch` est une dépendance pour useEffect, bien qu'elle soit stable.

  // Définition des colonnes pour la grille de données.
  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: 'Nom', width: 200 },
    { field: 'status', headerName: 'Statut', width: 150 },
    { field: 'created_at', headerName: 'Créé le', width: 150 },
  ];

  return (
    <div style={{ height: 400, width: '100%' }}>
      {/* Composant DataGrid de Material-UI pour afficher les tests */}
      <DataGrid
        rows={tests}
        columns={columns}
        pageSize={5} // Nombre de lignes par page.
        rowsPerPageOptions={[5, 10, 20]} // Options pour le nombre de lignes par page.
        checkboxSelection // Permet la sélection de lignes.
        disableSelectionOnClick // Empêche la sélection de ligne au clic sur une cellule.
      />
    </div>
  );
};

export default Tests;
