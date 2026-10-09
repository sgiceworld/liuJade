/**
 * 古玉鉴真 — 鉴定结果页
 * 展示年代 (top3) + 真伪判定 + 概率分布; 低置信时支持送服务器复核
 */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { ERA_NAMES } from '../../../../shared/constants/eras';
import { useAppStore } from '../store/useAppStore';
import { recheckOnServer } from '../services/identifyFlow';
import type { PendingResult } from './IdentifyScreen';

export function ResultScreen({
  route,
  navigation,
}: {
  route: { params: { pending: PendingResult } };
  navigation: { goBack: () => void };
}): React.JSX.Element {
  const serverBase = useAppStore(s => s.serverBase);
  const [pending, setPending] = useState(route.params.pending);
  const [rechecking, setRechecking] = useState(false);
  const [recheckError, setRecheckError] = useState('');

  const { result, source, lowConfidence } = pending;
  const top1Prob = result.era_probabilities[result.era_code] ?? 0;

  const bars = Object.entries(result.era_probabilities)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const doRecheck = async () => {
    setRechecking(true);
    setRecheckError('');
    try {
      const serverResult = await recheckOnServer(serverBase, pending.photoUri);
      setPending({ source: 'server', result: serverResult, lowConfidence: false, photoUri: pending.photoUri });
    } catch (e) {
      setRecheckError((e as Error).message);
    } finally {
      setRechecking(false);
    }
  };

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.container}>
      <Text style={styles.title}>鉴定结果</Text>
      <Text style={styles.sourceTag}>
        来源: {source === 'server' ? 'PC 服务器 (FP32)' : '端侧 (INT8)'}
        {lowConfidence ? ' · 低置信' : ''}
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>年代</Text>
        <Text style={styles.eraMain}>
          {result.predicted_era} ({result.era_code})
        </Text>
        <Text style={styles.prob}>{(top1Prob * 100).toFixed(1)}%</Text>

        <View style={styles.divider} />
        <Text style={styles.label}>真伪判定</Text>
        <Text
          style={[
            styles.authMain,
            result.predicted_authenticity === '真老'
              ? styles.authGenuine
              : styles.authFake,
          ]}>
          {result.predicted_authenticity}
        </Text>
        <Text style={styles.prob}>
          置信 {(result.authenticity_confidence * 100).toFixed(1)}%
        </Text>

        <View style={styles.divider} />
        <Text style={styles.label}>年代概率分布</Text>
        {bars.map(([code, prob]) => (
          <View key={code} style={styles.barRow}>
            <Text style={styles.barName}>
              {ERA_NAMES[code as keyof typeof ERA_NAMES]} ({code})
            </Text>
            <View style={styles.barTrack}>
              <View
                style={[
                  styles.barFill,
                  { width: `${(prob * 100).toFixed(0)}%` as `${number}%` },
                ]}
              />
            </View>
            <Text style={styles.barProb}>{(prob * 100).toFixed(1)}%</Text>
          </View>
        ))}
      </View>

      <Text style={styles.meta}>
        耗时 {result.inference_time_ms}ms · 编号 {result.label_code}
      </Text>
      {lowConfidence && !rechecking && (
        <>
          <Pressable style={styles.btn} onPress={doRecheck}>
            <Text style={styles.btnText}>📡 送服务器复核 (FP32)</Text>
          </Pressable>
          {recheckError ? (
            <Text style={styles.error}>❌ {recheckError}</Text>
          ) : null}
        </>
      )}
      {rechecking && <ActivityIndicator color="#8c6a3f" />}
      <Pressable style={styles.btnGhost} onPress={() => navigation.goBack()}>
        <Text style={styles.btnGhostText}>← 返回再鉴定一张</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210' },
  container: { padding: 20, gap: 14 },
  title: { color: '#e8d9b0', fontSize: 22, fontWeight: '700', textAlign: 'center' },
  sourceTag: { color: '#9a8d75', fontSize: 12, textAlign: 'center' },
  card: {
    backgroundColor: '#1e1a16',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#5a4f3e',
    padding: 16,
    gap: 6,
  },
  label: { color: '#9a8d75', fontSize: 13 },
  eraMain: { color: '#e8d9b0', fontSize: 30, fontWeight: '700' },
  authMain: { fontSize: 26, fontWeight: '700' },
  authGenuine: { color: '#7fb069' },
  authFake: { color: '#e07a5f' },
  prob: { color: '#b5a888', fontSize: 14 },
  divider: { height: 1, backgroundColor: '#3a322a', marginVertical: 8 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barName: { color: '#c9b98f', fontSize: 12, width: 130 },
  barTrack: {
    flex: 1,
    height: 10,
    backgroundColor: '#2a241e',
    borderRadius: 5,
    overflow: 'hidden',
  },
  barFill: { height: '100%', backgroundColor: '#8c6a3f' },
  barProb: { color: '#8a7d65', fontSize: 11, width: 46, textAlign: 'right' },
  meta: { color: '#6a5f4e', fontSize: 12, textAlign: 'center' },
  btn: {
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#8c6a3f',
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  btnGhost: { paddingVertical: 12, alignItems: 'center' },
  btnGhostText: { color: '#9a8d75', fontSize: 14 },
  error: { color: '#e88', fontSize: 13, textAlign: 'center' },
});
