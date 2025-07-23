// src/App.js
import React from 'react';
import { Provider } from 'react-redux';
import { store } from './redux/store';
import Layout from './components/Layout';
import Reports from './components/Reports';
import Tests from './components/Tests';
import ChatInterface from './components/ChatInterface';

const App = () => {
  return (
    <Provider store={store}>
      <Layout>
        <div>
          <h2>Assistant Conversationnel</h2>
          <ChatInterface />
          <h2>Reports</h2>
          <Reports />
          <h2>Tests</h2>
          <Tests />
        </div>
      </Layout>
    </Provider>
  );
};

export default App;