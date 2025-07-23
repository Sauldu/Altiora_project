// src/components/Reports.js
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchReports } from '../redux/reportsSlice';
import { DataGrid } from '@mui/x-data-grid';

const Reports = () => {
  const dispatch = useDispatch();
  const reports = useSelector(state => state.reports.reports);

  useEffect(() => {
    dispatch(fetchReports());
  }, [dispatch]);

  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'title', headerName: 'Title', width: 200 },
    { field: 'content', headerName: 'Content', width: 300 },
    { field: 'created_at', headerName: 'Created At', width: 150 },
  ];

  return (
    <div style={{ height: 400, width: '100%' }}>
      <DataGrid rows={reports} columns={columns} />
    </div>
  );
};

export default Reports;