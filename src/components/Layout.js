// src/components/Layout.js
import React from 'react';
import { AppBar, Toolbar, Typography } from '@mui/material';

const Layout = ({ children }) => {
  return (
    <div>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6">Altiora Dashboard</Typography>
        </Toolbar>
      </AppBar>
      <div>{children}</div>
    </div>
  );
};

export default Layout;