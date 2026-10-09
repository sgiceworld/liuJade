/**
 * 古玉鉴真 — 设置页: 服务器地址 + 健康检查 + 推理模式 + 端侧模型管理
 */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useAppStore, IdentifyMode } from '../store/useAppStore';
import { serverClient } from '../services/serverClient';
import { modelStore } from '../localInference/modelStore';

const MODES: Array<{ id: IdentifyMode; label: string }> = [
  { id: 'auto', label: '本地优先 + 服务器回退' },
  { id: 'local', label: '仅本地 (INT8)' },
  { id: 'server', label: '仅服务器 (FP32)' },
];

export function SettingsScreen(): React.JSX.Element {
  const { serverBase, setServerBase, serverHealthy, setServerHealthy, identifyMode, setIdentifyMode } =
    useAppStore();
  const [draft, setDraft] = useState(serverBase);
  const [checking, setChecking] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [localReady, setLocalReady] = useState(false);

  const checkHealth = async () => {
    setChecking(true);
    try {
      const health = await serverClient.health(draft);
      setServerHealthy(health.status === 'ok');
    } catch {
      setServerHealthy(false);
    } finally {
      setChecking(false);
    }
  };

  const refreshLocalState = async () => {
    setLocalReady(await modelStore.isReady());
  };
  refreshLocalState();

  const syncModels = async () => {
    setSyncing(true);
    setSyncMsg('');
    try {
      await modelStore.sync(draft, p =>
        setSyncMsg(`下载中 ${p.done}/${p.total}`),
      );
      setSyncMsg('✓ 模型同步完成');
      await refreshLocalState();
    } catch (e) {
      setSyncMsg(`❌ ${(e as Error).message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <View style={styles.page}>
      <Text style={styles.title}>⚙️ 设置</Text>

      <Text style={styles.label}>推理模式</Text>
      <View style={styles.modeRow}>
        {MODES.map(m => (
          <Pressable
            key={m.id}
            style={[styles.modeChip, identifyMode === m.id && styles.modeChipActive]}
            onPress={() => setIdentifyMode(m.id)}>
            <Text
              style={[
                styles.modeChipText,
                identifyMode === m.id && styles.modeChipTextActive,
              ]}>
              {m.label}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>PC 服务器地址</Text>
      <TextInput
        style={styles.input}
        value={draft}
        onChangeText={setDraft}
        placeholder="http://10.0.2.2:8720"
        placeholderTextColor="#6a5f4e"
        autoCapitalize="none"
        autoCorrect={false}
      />
      <Text style={styles.hint}>
        模拟器默认 10.0.2.2:8720{'\n'}
        真机 USB: adb reverse tcp:8720 tcp:8720 后用 localhost:8720{'\n'}
        真机 LAN: PC 局域网 IP (服务器 JADE_HOST=0.0.0.0 启动)
      </Text>

      <Pressable style={styles.btn} onPress={() => setServerBase(draft)}>
        <Text style={styles.btnText}>保存</Text>
      </Pressable>
      <Pressable
        style={[styles.btn, styles.btnSecondary]}
        onPress={checkHealth}
        disabled={checking}>
        <Text style={styles.btnText}>
          {checking
            ? '检查中...'
            : serverHealthy
            ? '✓ 服务器健康'
            : '检查服务器连接'}
        </Text>
      </Pressable>

      <Text style={styles.label}>
        端侧模型 {localReady ? '(✓ 已就绪)' : '(未下载)'}
      </Text>
      <Pressable
        style={[styles.btn, styles.btnSecondary]}
        onPress={syncModels}
        disabled={syncing}>
        {syncing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>下载/校验 INT8 模型</Text>
        )}
      </Pressable>
      {syncMsg ? <Text style={styles.syncMsg}>{syncMsg}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210', padding: 20, gap: 12 },
  title: { color: '#e8d9b0', fontSize: 22, fontWeight: '700' },
  label: { color: '#c9b98f', fontSize: 14, marginTop: 6 },
  modeRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  modeChip: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#5a4f3e',
    backgroundColor: '#1e1a16',
  },
  modeChipActive: { backgroundColor: '#8c6a3f', borderColor: '#8c6a3f' },
  modeChipText: { color: '#9a8d75', fontSize: 12 },
  modeChipTextActive: { color: '#fff', fontWeight: '600' },
  input: {
    backgroundColor: '#1e1a16',
    borderColor: '#5a4f3e',
    borderWidth: 1,
    borderRadius: 8,
    color: '#e8d9b0',
    padding: 10,
    fontSize: 14,
  },
  hint: { color: '#6a5f4e', fontSize: 12, lineHeight: 18 },
  btn: {
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#8c6a3f',
    alignItems: 'center',
  },
  btnSecondary: { backgroundColor: '#3a322a' },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  syncMsg: { color: '#b5a888', fontSize: 12, textAlign: 'center' },
});
