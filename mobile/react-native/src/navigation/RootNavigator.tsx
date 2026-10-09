/**
 * 古玉鉴真 — 根导航: bottom-tab (鉴定/图鉴/采集/设置) + Stack (结果/藏品详情)
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { IdentifyScreen, PendingResult } from '../screens/IdentifyScreen';
import { ResultScreen } from '../screens/ResultScreen';
import { GalleryScreen } from '../screens/GalleryScreen';
import { PieceDetailScreen } from '../screens/PieceDetailScreen';
import { CollectScreen } from '../screens/CollectScreen';
import { SettingsScreen } from '../screens/SettingsScreen';

export type RootStackParamList = {
  Tabs: undefined;
  Result: { pending: PendingResult };
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const GalleryStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const darkHeader = {
  headerStyle: { backgroundColor: '#1e1a16' },
  headerTintColor: '#e8d9b0',
};

/** 图鉴 Tab 内嵌栈: 列表 → 详情 */
function GalleryTab() {
  return (
    <GalleryStack.Navigator screenOptions={darkHeader}>
      <GalleryStack.Screen
        name="GalleryList"
        component={GalleryScreen as any}
        options={{ headerShown: false }}
      />
      <GalleryStack.Screen
        name="PieceDetail"
        component={PieceDetailScreen as any}
        options={{ title: '藏品详情' }}
      />
    </GalleryStack.Navigator>
  );
}

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: '#1e1a16', borderTopColor: '#3a322a' },
        tabBarActiveTintColor: '#e8d9b0',
        tabBarInactiveTintColor: '#6a5f4e',
      }}>
      <Tab.Screen
        name="Identify"
        options={{ tabBarLabel: '鉴定', tabBarIcon: () => null }}>
        {({ navigation }) => (
          <IdentifyScreen
            onResult={r =>
              navigation.getParent()?.navigate('Result', { pending: r })
            }
          />
        )}
      </Tab.Screen>
      <Tab.Screen
        name="Gallery"
        component={GalleryTab}
        options={{ tabBarLabel: '图鉴', tabBarIcon: () => null }}
      />
      <Tab.Screen
        name="Collect"
        component={CollectScreen}
        options={{ tabBarLabel: '采集', tabBarIcon: () => null }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarLabel: '设置', tabBarIcon: () => null }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator(): React.JSX.Element {
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={darkHeader}>
        <Stack.Screen
          name="Tabs"
          component={Tabs}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="Result"
          component={ResultScreen as any}
          options={{ title: '鉴定结果' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
