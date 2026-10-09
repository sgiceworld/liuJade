/**
 * 古玉鉴真 — 移动端 (React Native)
 */

import React from 'react';
import { StatusBar } from 'react-native';
import { RootNavigator } from './src/navigation/RootNavigator';

function App(): React.JSX.Element {
  return (
    <>
      <StatusBar barStyle="light-content" backgroundColor="#141210" />
      <RootNavigator />
    </>
  );
}

export default App;
