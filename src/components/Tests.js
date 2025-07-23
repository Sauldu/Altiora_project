// src/components/Tests.js
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchTests } from '../redux/testsSlice';
import { DataGrid } from '@mui/x-data-grid';

const Tests = () => {
  const dispatch = useDispatch();
  const tests = useSelector(state => state.tests.tests);

  useEffect(() => {
    dispatch(fetchTests());
  }, [dispatch]);

  const columns = [
    { field: 'id', headerName: 'ID', width: 70 },
    { field: 'name', headerName: 'Name', width: 200 },
    { field: 'status', headerName: 'Status', width: 150 },
    { field: 'created_at', headerName: 'Created At', width: 150 },
  ];

  return (
    <div style={{ height: 400, width: '100%' }}>
      <DataGrid rows={tests} columns={columns} />
    </div>
  );
};

export default Tests;