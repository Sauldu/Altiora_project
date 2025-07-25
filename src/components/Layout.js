// src/components/Layout.js
import React from 'react';
import { AppBar, Toolbar, Typography } from '@mui/material';

/**
 * @file Composant de mise en page principal pour l'application Altiora.
 * @module components/Layout
 */

/**
 * Composant `Layout`.
 * 
 * Ce composant fournit la structure de base de l'interface utilisateur de l'application,
 * incluant une barre d'application (AppBar) en haut et un espace pour le contenu enfant.
 * Il utilise les composants Material-UI pour une apparence cohérente.
 * 
 * @param {object} props - Les propriétés du composant.
 * @param {React.ReactNode} props.children - Le contenu à afficher à l'intérieur de la mise en page.
 * @returns {JSX.Element} Le composant de mise en page.
 */
const Layout = ({ children }) => {
  return (
    <div>
      {/* Barre d'application en haut de la page */}
      <AppBar position="static">
        <Toolbar>
          {/* Titre du tableau de bord */}
          <Typography variant="h6">Altiora Dashboard</Typography>
        </Toolbar>
      </AppBar>
      {/* Contenu principal de la page */}
      <div>{children}</div>
    </div>
  );
};

export default Layout;
