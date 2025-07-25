// src/components/Reports.js
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchReports } from '../redux/reportsSlice';
import { DataGrid } from '@mui/x-data-grid';

/**
 * @file Composant d'affichage des rapports pour l'application Altiora.
 * @module components/Reports
 */

/**
 * Composant `Reports`.
 * 
 * Ce composant React affiche une liste de rapports dans une grille de données.
 * Il utilise Redux pour gérer l'état des rapports et Material-UI DataGrid pour l'affichage.
 * Les rapports sont récupérés au montage du composant via l'action `fetchReports`.
 * 
 * @returns {JSX.Element} Le composant d'affichage des rapports.
 */
const Reports = () => {
  // Hook pour dispatcher des actions Redux.
  const dispatch = useDispatch();
  // Hook pour sélectionner des données depuis le store Redux.
  const reports = useSelector(state => state.reports.reports);

  // Effet de bord pour récupérer les rapports au montage du composant.
  useEffect(() => {
    /**
     * Dispatch l'action `fetchReports` pour charger les données des rapports.
     * Cette action est exécutée une seule fois au montage du composant.
     */
    dispatch(fetchReports());
  }, [dispatch]); // `dispatch` est une dépendance pour useEffect, bien qu'elle soit stable.

  // Définition des colonnes pour la grille de données.
  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'title', headerName: 'Titre', width: 200 },
    { field: 'content', headerName: 'Contenu', width: 300 },
    { field: 'created_at', headerName: 'Créé le', width: 150 },
  ];

  return (
    <div style={{ height: 400, width: '100%' }}>
      {/* Composant DataGrid de Material-UI pour afficher les rapports */}
      <DataGrid
        rows={reports}
        columns={columns}
        pageSize={5} // Nombre de lignes par page.
        rowsPerPageOptions={[5, 10, 20]} // Options pour le nombre de lignes par page.
        checkboxSelection // Permet la sélection de lignes.
        disableSelectionOnClick // Empêche la sélection de ligne au clic sur une cellule.
      />
    </div>
  );
};

export default Reports;
