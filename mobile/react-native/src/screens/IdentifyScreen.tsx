/**
 * 古玉鉴真 — 现场拍照鉴定
 * 混合流程: 本地 INT8 优先 → 失败/低置信回退 PC 服务器 (identifyFlow)
 */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { launchImageLibrary } from 'react-native-image-picker';
import { useAppStore } from '../store/useAppStore';
import { identify } from '../services/identifyFlow';
import type { ServerAuthResult } from '../services/serverClient';

export interface PendingResult {
  source: 'server' | 'local';
  result: ServerAuthResult;
  lowConfidence: boolean;
  photoUri: string;
}

type Props = {
  onResult: (r: PendingResult) => void;
};

export function IdentifyScreen({ onResult }: Props): React.JSX.Element {
  const serverBase = useAppStore(s => s.serverBase);
  const identifyMode = useAppStore(s => s.identifyMode);
  const [photoUri, setPhotoUri] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const pickPhoto = () => {
    setError('');
    launchImageLibrary(
      { mediaType: 'photo', selectionLimit: 1, includeBase64: false },
      res => {
        if (res.didCancel) return;
        if (res.errorCode) {
          setError(`选图失败: ${res.errorMessage || res.errorCode}`);
          return;
        }
        const asset = res.assets?.[0];
        if (asset?.uri) setPhotoUri(asset.uri);
      },
    );
  };

  const runIdentify = async () => {
    if (!photoUri) return;
    setBusy(true);
    setError('');
    try {
      const outcome = await identify(serverBase, photoUri, identifyMode);
      onResult({ ...outcome, photoUri });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.container}>
      <Text style={styles.title}>🔍 现场鉴定</Text>
      <Text style={styles.subtitle}>
        拍摄或选择玉器照片 · 模式: {identifyMode === 'auto' ? '本地优先+服务器回退' : identifyMode === 'local' ? '仅本地 INT8' : '仅服务器'}
      </Text>

      <Pressable style={styles.photoBox} onPress={pickPhoto}>
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.photo} />
        ) : (
          <Text style={styles.photoHint}>📷 选择照片</Text>
        )}
      </Pressable>

      {error ? <Text style={styles.error}>❌ {error}</Text> : null}

      <Pressable
        style={[styles.btn, (!photoUri || busy) && styles.btnDisabled]}
        onPress={runIdentify}
        disabled={!photoUri || busy}>
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>开始鉴定</Text>
        )}
      </Pressable>
      <View style={styles.serverInfo}>
        <Text style={styles.serverText}>服务器: {serverBase}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#141210' },
  container: { padding: 20, alignItems: 'center', gap: 16 },
  title: { color: '#e8d9b0', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#9a8d75', fontSize: 13, textAlign: 'center' },
  photoBox: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#5a4f3e',
    backgroundColor: '#1e1a16',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photo: { width: '100%', height: '100%' },
  photoHint: { color: '#8a7d65', fontSize: 16 },
  btn: {
    width: '100%',
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#8c6a3f',
    alignItems: 'center',
  },
  btnDisabled: { opacity: 0.4 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  error: { color: '#e88', fontSize: 14, textAlign: 'center' },
  serverInfo: { marginTop: 8 },
  serverText: { color: '#6a5f4e', fontSize: 12 },
});
